import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "windows-app"))
from blog_gui.services import Services, ServiceError
from blog_gui.storage import Settings, Store
from blog_gui.workflow import author_locally


def test_local_authoring_without_server_and_repeated_topic(tmp_path):
    def no_network():
        pytest.fail("Local Mock workflow must never contact the network")
    service = Services(Store(tmp_path), no_network)
    config = Settings(scheduled_image=True)
    first = author_locally(service, config, "")
    second = author_locally(service, config, "")
    assert first["article"]["id"] != second["article"]["id"]
    assert len(first["article"]["images"]) == 1
    with zipfile.ZipFile(first["path"]) as archive:
        assert {"index.html", "article.docx", "article.txt", "manifest.json"} <= set(archive.namelist())
        assert len(json.loads(archive.read("manifest.json"))["image_order"]) == 1
    assert service.store.get("last_authoring_run")["status"] == "completed"
    assert not service.store.get("uploaded:" + first["article"]["id"])


def test_real_automatic_mode_requires_key(tmp_path):
    service = Services(Store(tmp_path))
    with pytest.raises(ServiceError, match="API 키"):
        author_locally(service, Settings(mock=False), "")
    assert service.store.articles() == []


def test_event_queue_failure_does_not_cancel_local_output(tmp_path, monkeypatch):
    service = Services(Store(tmp_path))
    def unavailable(*args):
        raise OSError("queue unavailable")
    monkeypatch.setattr(service.outbox, "enqueue", unavailable)
    result = author_locally(service, Settings(), "")
    assert Path(result["path"]).is_file()
    assert service.store.logs("WARNING")


def test_image_failure_preserves_article_and_reports_stage(tmp_path, monkeypatch):
    service = Services(Store(tmp_path))
    def fail(*args):
        raise ServiceError("image request failed")
    monkeypatch.setattr(service, "generate_image", fail)
    with pytest.raises(ServiceError):
        author_locally(service, Settings(scheduled_image=True), "")
    state = service.store.get("last_authoring_run")
    assert state["status"] == "failed" and "이미지" in state["stage"]
    assert service.store.articles()[0]["id"] == state["article_id"]
