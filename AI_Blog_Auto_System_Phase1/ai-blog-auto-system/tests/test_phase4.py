import hashlib
import io
import json
import os
import sqlite3
import sys
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ubuntu-server"))
sys.path.insert(0, str(ROOT / "windows-app"))
from app.main import create_app
from blog_gui.exports import Publication

TOKEN = "package-test-token"
AUTH = {"X-Device-Token": TOKEN}


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 18, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


@pytest.fixture
def package(tmp_path):
    from PIL import Image
    images = []
    for i, color in enumerate(("blue", "red", "green")):
        path = tmp_path / f"{i}.png"
        Image.new("RGB", (20, 20), color).save(path)
        images.append({"id": str(uuid.uuid4()), "path": str(path), "caption": color, "disclosure": "Mock"})
    article = {"id": str(uuid.uuid4()), "created_at": "2026-11-18T00:00:00+00:00",
               "title": "수동 발행 시험", "summary": "테스트", "sections": [{"heading": "본문", "body": "내용"}],
               "images": images, "sources": [], "tags": [], "seo_keywords": []}
    return Publication(article).package()


@pytest.fixture
def server(tmp_path):
    clock = Clock()
    app = create_app(tmp_path / "events.db", TOKEN, package_dir=tmp_path / "private", clock=clock)
    with TestClient(app) as client:
        yield client, app.state.packages, clock


def upload(client, data, **headers):
    return client.post("/api/v1/packages", content=data, headers={**AUTH, "Content-Type": "application/zip",
                       "X-Content-SHA256": hashlib.sha256(data).hexdigest(), **headers})


def events(client):
    return [x["event_type"] for x in client.get("/api/v1/events", headers=AUTH).json()]


def rewrite(data, transform):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    transform(files)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return stream.getvalue()


def test_roundtrip_all_formats_and_order(server, package):
    client, store, clock = server
    result = upload(client, package)
    assert result.status_code == 200, result.text
    metadata = result.json()
    assert metadata["new"]
    assert datetime.fromisoformat(metadata["expires_at"]) == clock.now + timedelta(hours=48)
    url = f'/api/v1/packages/{metadata["package_id"]}/download'
    response = client.get(url, headers=AUTH)
    assert response.content == package
    assert response.headers["cache-control"] == "no-store, private"
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        for kind, name in (("html", "index.html"), ("docx", "article.docx"),
                           ("txt", "article.txt"), ("manifest", "manifest.json")):
            assert client.get(url, params={"kind": kind}, headers=AUTH).content == archive.read(name)
        manifest = json.loads(archive.read("manifest.json"))
        for i, name in enumerate(manifest["image_order"]):
            assert client.get(url, params={"kind": "image", "image_index": i}, headers=AUTH).content == archive.read(name)
    assert client.get(url, params={"kind": "image", "image_index": 3}, headers=AUTH).status_code == 404
    with closing(store.connect()) as db:
        assert db.execute("SELECT count(*) FROM package_downloads").fetchone()[0] == 8
    assert list(store.root.iterdir())[0].suffix == ".zip"
    assert events(client).count("PACKAGE_UPLOAD_SUCCESS") == 1


def test_auth_limits_hash_and_parameters(server, package, tmp_path):
    client, _, _ = server
    for method, url in (("post", "/api/v1/packages"), ("get", "/api/v1/packages"),
                        ("get", f"/api/v1/packages/{uuid.uuid4()}/download")):
        assert getattr(client, method)(url).status_code == 401
        assert getattr(client, method)(url, headers={"X-Device-Token": "wrong"}).status_code == 401
    assert upload(client, package, **{"X-Content-SHA256": "0" * 64}).status_code == 422
    assert upload(client, package, **{"Content-Type": "text/plain"}).status_code == 415
    assert upload(client, package, **{"Content-Length": "invalid"}).status_code == 400
    with TestClient(create_app(tmp_path / "small.db", TOKEN, max_package_bytes=10)) as small:
        assert upload(small, package).status_code == 413
        response = small.post("/api/v1/packages", content=iter([b"a" * 6, b"b" * 6]),
                              headers={**AUTH, "Content-Type": "application/zip", "X-Content-SHA256": "0" * 64})
        assert response.status_code == 413
    assert client.get("/api/v1/packages/not-uuid/download", headers=AUTH).status_code == 422
    assert client.get(f"/api/v1/packages/{uuid.uuid4()}/download", headers=AUTH).status_code == 404


def test_duplicate_conflict_concurrent_no_extension(server, package):
    client, store, clock = server
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: upload(client, package), range(4)))
    assert all(r.status_code == 200 for r in results)
    assert sum(r.json()["new"] for r in results) == 1
    original = results[0].json()["expires_at"]
    clock.now += timedelta(hours=3)
    assert upload(client, package).json()["expires_at"] == original
    changed = rewrite(package, lambda f: f.update({"manifest.json": f["manifest.json"] + b" "}))
    assert upload(client, changed).status_code == 409
    assert len(list(store.root.iterdir())) == 1


def test_expiry_boundary_immediate_denial_then_delete(server, package):
    client, store, clock = server
    metadata = upload(client, package).json()
    url = f'/api/v1/packages/{metadata["package_id"]}/download'
    clock.now += timedelta(hours=48) - timedelta(microseconds=1)
    assert client.get(url, headers=AUTH).status_code == 200
    clock.now += timedelta(microseconds=1)
    assert client.get(url, headers=AUTH).status_code == 410
    assert client.get(url, headers=AUTH, params={"kind": "html"}).status_code == 410
    assert upload(client, package).status_code == 410
    assert len(list(store.root.iterdir())) == 1  # No cleanup has run yet.
    store.maintain()
    store.maintain()
    assert list(store.root.iterdir()) == []
    assert events(client).count("PACKAGE_DELETED") == 1
    assert client.get("/api/v1/packages", headers=AUTH).json()[0]["deleted_at"]


def test_reminders_exact_thresholds_restart_and_dedup(server, package):
    client, store, clock = server
    upload(client, package)
    clock.now += timedelta(hours=42) - timedelta(microseconds=1)
    store.maintain()
    assert "PACKAGE_EXPIRING_6H" not in events(client)
    clock.now += timedelta(microseconds=1)
    store.maintain()
    store.maintain()
    assert events(client).count("PACKAGE_EXPIRING_6H") == 1
    clock.now += timedelta(hours=5)
    from app.packages import PackageStore
    restarted = PackageStore(store.connect, store.root, clock)
    restarted.maintain()
    restarted.maintain()
    assert events(client).count("PACKAGE_EXPIRING_1H") == 1
    assert events(client).count("PACKAGE_EXPIRING_6H") == 1


def test_delete_failure_retry_and_missing_file(server, package, monkeypatch):
    client, store, clock = server
    metadata = upload(client, package).json()
    clock.now += timedelta(hours=48)
    original = Path.unlink
    def locked(path, *args, **kwargs):
        if path.parent == store.root:
            raise PermissionError("simulated locked file")
        return original(path, *args, **kwargs)
    with monkeypatch.context() as m:
        m.setattr(Path, "unlink", locked)
        store.maintain()
        assert "PACKAGE_DELETED" not in events(client)
        assert client.get(f'/api/v1/packages/{metadata["package_id"]}/download', headers=AUTH).status_code == 410
    # Simulate crash after unlink but before DB commit; absent files must be retryable.
    list(store.root.iterdir())[0].unlink()
    store.maintain()
    assert events(client).count("PACKAGE_DELETED") == 1
    assert not any(e.startswith("PACKAGE_EXPIRING") for e in events(client))


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "images/../bad.png", "images\\x.png", "extra.exe"])
def test_traversal_and_extra_members_rejected(server, package, name):
    client, store, _ = server
    assert upload(client, rewrite(package, lambda f: f.update({name: b"bad"}))).status_code == 422
    assert list(store.root.iterdir()) == []


def test_corruption_manifest_order_and_type_rejected(server, package):
    client, _, _ = server
    assert upload(client, b"not a zip").status_code == 422
    assert upload(client, rewrite(package, lambda f: f.update({"article.txt": b"tampered"}))).status_code == 422
    def bad_manifest(files):
        manifest = json.loads(files["manifest.json"])
        manifest["image_order"].reverse()
        files["manifest.json"] = json.dumps(manifest).encode()
    assert upload(client, rewrite(package, bad_manifest)).status_code == 422
    def fake_type(files):
        files["article.docx"] = b"not-docx"
        manifest = json.loads(files["manifest.json"])
        for entry in manifest["files"]:
            if entry["path"] == "article.docx":
                entry.update(size=8, sha256=hashlib.sha256(b"not-docx").hexdigest())
        files["manifest.json"] = json.dumps(manifest).encode()
    assert upload(client, rewrite(package, fake_type)).status_code == 422


def test_duplicate_zip_symlink_and_bomb_rejected(server, package, monkeypatch):
    client, _, _ = server
    output = io.BytesIO(package)
    with zipfile.ZipFile(output, "a") as archive:
        with pytest.warns(UserWarning):
            archive.writestr("article.txt", "duplicate")
    assert upload(client, output.getvalue()).status_code == 422
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(package)) as source, zipfile.ZipFile(output, "w") as dest:
        for item in source.infolist():
            if item.filename == "article.txt":
                item.create_system = 3
                item.external_attr = 0o120777 << 16
            dest.writestr(item, source.read(item))
    assert upload(client, output.getvalue()).status_code == 422
    monkeypatch.setattr("app.packages.MAX_EXPANDED", 100)
    assert upload(client, package).status_code == 422


def test_storage_corruption_orphan_and_write_failure(server, package, monkeypatch):
    client, store, _ = server
    with monkeypatch.context() as m:
        m.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("disk full")))
        with pytest.raises(OSError):
            upload(client, package)
    assert list(store.root.iterdir()) == []
    assert client.get("/api/v1/packages", headers=AUTH).json() == []
    metadata = upload(client, package).json()
    list(store.root.iterdir())[0].write_bytes(b"corrupt")
    assert client.get(f'/api/v1/packages/{metadata["package_id"]}/download', headers=AUTH).status_code == 503
    orphan = store.root / (uuid.uuid4().hex + ".zip")
    orphan.write_bytes(b"incomplete-upload")
    unrelated = store.root / "do-not-touch.txt"
    unrelated.write_text("test")
    store.maintain()
    assert not orphan.exists()
    assert unrelated.exists()


def test_completion_clock_after_fsync(server, package, monkeypatch):
    client, _, clock = server
    initial = clock.now
    real_fsync = os.fsync
    def slow_disk(fd):
        real_fsync(fd)
        clock.now += timedelta(minutes=7)
    monkeypatch.setattr(os, "fsync", slow_disk)
    metadata = upload(client, package).json()
    assert datetime.fromisoformat(metadata["uploaded_at"]) == initial + timedelta(minutes=7)
    assert datetime.fromisoformat(metadata["expires_at"]) == clock.now + timedelta(hours=48)


def test_actual_periodic_worker_and_restart(tmp_path, package):
    clock = Clock()
    db_path = tmp_path / "periodic.db"
    app = create_app(db_path, TOKEN, clock=clock, maintenance_interval=0.03)
    with TestClient(app) as client:
        metadata = upload(client, package).json()
        clock.now += timedelta(hours=48)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if "PACKAGE_DELETED" in events(client):
                break
            time.sleep(0.02)
        else:
            pytest.fail("Periodic cleanup did not run")
    with TestClient(create_app(db_path, TOKEN, clock=clock)) as restarted:
        assert restarted.get(f'/api/v1/packages/{metadata["package_id"]}/download', headers=AUTH).status_code == 410
        assert events(restarted).count("PACKAGE_DELETED") == 1


def test_backup_contains_metadata_only_and_no_recoverable_package(server, package, tmp_path):
    from backup_metadata import backup_metadata
    client, store, clock = server
    upload(client, package)
    with closing(store.connect()) as db:
        source = Path(db.execute("PRAGMA database_list").fetchone()[2])
    backup = tmp_path / "backups"
    backup.mkdir()
    target = backup / "metadata.sqlite3"
    backup_metadata(source, target)
    with closing(sqlite3.connect(target)) as db:
        assert db.execute("SELECT count(*) FROM packages").fetchone()[0] == 1
        assert {r[1] for r in db.execute("PRAGMA table_info(packages)")} == {
            "package_id", "sha256", "size", "filename", "uploaded_at", "expires_at", "deleted_at"}
    assert list(backup.iterdir()) == [target]
    assert package not in target.read_bytes()
    with pytest.raises(FileExistsError):
        backup_metadata(source, target)
    clock.now += timedelta(hours=48)
    store.maintain()
    assert not list(store.root.iterdir())


def test_missing_file_and_unsafe_database_path(server, package, tmp_path):
    client, store, _ = server
    metadata = upload(client, package).json()
    url = f'/api/v1/packages/{metadata["package_id"]}/download'
    stored = next(store.root.glob("*.zip"))
    stored.unlink()
    assert client.get(url, headers=AUTH).status_code == 503
    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"do not delete")
    with closing(store.connect()) as db, db:
        db.execute("UPDATE packages SET filename=?,expires_at=?", ("../outside.zip", "2000-01-01T00:00:00+00:00"))
    store.maintain()
    assert outside.read_bytes() == b"do not delete"
    assert "PACKAGE_DELETED" not in events(client)


def test_late_start_catches_up_reminders_once(server, package):
    client, store, clock = server
    upload(client, package)
    clock.now += timedelta(hours=47, minutes=30)
    store.maintain()
    store.maintain()
    assert events(client).count("PACKAGE_EXPIRING_6H") == 1
    assert events(client).count("PACKAGE_EXPIRING_1H") == 1


def test_stored_symlink_is_neither_read_nor_deleted(server, package, monkeypatch):
    client, store, clock = server
    metadata = upload(client, package).json()
    stored = next(store.root.glob("*.zip"))
    original = Path.is_symlink
    # Emulate a substituted link without requiring Windows CreateSymbolicLink privilege.
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == stored or original(path))
    assert client.get(f'/api/v1/packages/{metadata["package_id"]}/download', headers=AUTH).status_code == 503
    clock.now += timedelta(hours=48)
    store.maintain()
    assert stored.exists()
    assert "PACKAGE_DELETED" not in events(client)
