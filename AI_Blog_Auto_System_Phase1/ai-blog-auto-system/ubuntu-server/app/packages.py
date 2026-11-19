"""Private, bounded ZIP storage. Nothing is extracted or served as active HTML."""
import asyncio
import hashlib
import io
import json
import logging
import os
import re
import stat
import uuid
import zipfile
import zlib
from contextlib import closing, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from fastapi import Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response

LOG = logging.getLogger(__name__)
RETENTION = timedelta(hours=48)
MAX_BYTES = 100 * 1024 * 1024
MAX_EXPANDED = 120 * 1024 * 1024
IMAGE = re.compile(r"images/(thumbnail|body_[0-9]{2})\.png\Z")
STORED = re.compile(r"[0-9a-f]{32}\.zip\Z")


def utcnow():
    return datetime.now(timezone.utc)


def validate_type(name, data):
    if name.endswith(".png"):
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 20 * 1024 * 1024:
            raise ValueError("Expected PNG")
        offset = 8
        seen_header = False
        seen_data = False
        while offset + 12 <= len(data):
            size = int.from_bytes(data[offset:offset + 4], "big")
            kind = data[offset + 4:offset + 8]
            end = offset + 8 + size
            if end + 4 > len(data) or zlib.crc32(data[offset + 4:end]) != int.from_bytes(data[end:end + 4], "big"):
                raise ValueError("Invalid PNG chunk")
            if not seen_header:
                if kind != b"IHDR" or size != 13:
                    raise ValueError("Invalid PNG header")
                width = int.from_bytes(data[offset + 8:offset + 12], "big")
                height = int.from_bytes(data[offset + 12:offset + 16], "big")
                if not width or not height or width * height > 24_000_000:
                    raise ValueError("PNG pixel limit")
                seen_header = True
            seen_data = seen_data or kind == b"IDAT"
            offset = end + 4
            if kind == b"IEND":
                if size or offset != len(data) or not seen_data:
                    raise ValueError("Invalid PNG ending")
                return
        raise ValueError("Missing PNG ending")
    elif name.endswith(".docx"):
        with zipfile.ZipFile(io.BytesIO(data)) as docx:
            entries = docx.infolist()
            names = docx.namelist()
            if (len(entries) > 200 or len(set(names)) != len(names)
                    or sum(e.file_size for e in entries) > 64 * 1024 * 1024
                    or not {"[Content_Types].xml", "word/document.xml", "_rels/.rels"}.issubset(names)
                    or any("vba" in n.lower() or "embeddings/" in n.lower() for n in names)):
                raise ValueError("Invalid DOCX")
            for entry in entries:
                if (entry.flag_bits & 1 or entry.compress_type not in (0, 8)
                        or entry.filename.startswith("/") or "\\" in entry.filename
                        or ":" in entry.filename or ".." in entry.filename.split("/")):
                    raise ValueError("Unsupported DOCX entry")
                content = docx.read(entry)
                if entry.filename.endswith((".xml", ".rels")):
                    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                        raise ValueError("XML entities forbidden")
                    root = ET.fromstring(content)
                    if entry.filename == "word/document.xml" and root.tag != "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document":
                        raise ValueError("Invalid Word document")
                    if entry.filename == "[Content_Types].xml" and b"macroenabled" in content.lower():
                        raise ValueError("Macro-enabled document forbidden")
                    if any(node.get("TargetMode") == "External" and
                           not node.get("Type", "").endswith("/hyperlink") for node in root.iter()):
                        raise ValueError("External DOCX resource")
    else:
        text = data.decode("utf-8")
        if name.endswith(".html") and not re.search(r"<html(?:\s|>)", text, re.I):
            raise ValueError("Expected HTML")


def validate_package(data):
    """Validate CRC, exact manifest membership, sizes and hashes without extraction."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            names = [item.filename for item in members]
            required = {"manifest.json", "index.html", "article.txt", "article.docx"}
            if (len(members) > 34 or len(set(names)) != len(names)
                    or not required.issubset(names)
                    or any(n not in required and not IMAGE.fullmatch(n) for n in names)
                    or sum(i.file_size for i in members) > MAX_EXPANDED):
                raise ValueError("Invalid ZIP membership or expanded size")
            for item in members:
                mode = item.external_attr >> 16
                if (item.orig_filename != item.filename or item.flag_bits & 1
                        or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))):
                    raise ValueError("Unsupported ZIP entry")
            if archive.getinfo("manifest.json").file_size > 256 * 1024:
                raise ValueError("Manifest too large")
            manifest = json.loads(archive.read("manifest.json"))
            content_id = str(uuid.UUID(manifest["content_id"]))
            if manifest["format_version"] != "1.0":
                raise ValueError("Unsupported format version")
            files = manifest["files"]
            if not isinstance(files, list) or len(files) != len(names) - 1:
                raise ValueError("Invalid file manifest")
            by_name = {entry["path"]: entry for entry in files}
            if set(by_name) != set(names) - {"manifest.json"}:
                raise ValueError("Manifest membership mismatch")
            order = manifest["image_order"]
            if (not isinstance(order, list) or len(set(order)) != len(order)
                    or set(order) != {n for n in names if IMAGE.fullmatch(n)}
                    or [i["path"] for i in manifest["images"]] != order):
                raise ValueError("Image order mismatch")
            for name, entry in by_name.items():
                if type(entry["size"]) is not int or entry["size"] != archive.getinfo(name).file_size:
                    raise ValueError("File size mismatch")
                digest = hashlib.sha256()
                with archive.open(name) as source:
                    while chunk := source.read(65536):
                        digest.update(chunk)
                if digest.hexdigest() != entry["sha256"]:
                    raise ValueError("File checksum mismatch")
                validate_type(name, archive.read(name))
            for item in manifest["images"]:
                if item["sha256"] != by_name[item["path"]]["sha256"]:
                    raise ValueError("Image checksum mismatch")
            return content_id
    except (ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile,
            NotImplementedError, RuntimeError, EOFError, OSError, zlib.error, ET.ParseError) as exc:
        raise HTTPException(422, "Invalid content package") from exc


class PackageStore:
    def __init__(self, connect, root, clock=utcnow, max_bytes=MAX_BYTES):
        self.connect = connect
        self.root = Path(root).absolute()
        self.clock = clock
        self.max_bytes = max_bytes

    def initialize(self):
        if self.root.is_symlink():
            raise RuntimeError("Package directory must not be a symbolic link")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS packages (
                package_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
                filename TEXT NOT NULL UNIQUE, uploaded_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, deleted_at TEXT)""")
            db.execute("CREATE INDEX IF NOT EXISTS package_expiry ON packages(expires_at)")
            db.execute("""CREATE TABLE IF NOT EXISTS package_downloads (
                id INTEGER PRIMARY KEY, package_id TEXT NOT NULL, kind TEXT NOT NULL,
                downloaded_at TEXT NOT NULL)""")

    def file_path(self, name):
        if not STORED.fullmatch(name):
            raise RuntimeError("Invalid stored filename")
        path = self.root / name
        if path.is_symlink() or path.resolve().parent != self.root.resolve():
            raise RuntimeError("Unsafe stored path")
        return path

    def event(self, db, row, kind, now):
        # Transactional, deterministic event IDs make multi-worker/restart retries safe.
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "blog-package:" + row["package_id"] + ":" + kind))
        payload = json.dumps({"package_id": row["package_id"], "expires_at": row["expires_at"]})
        db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)",
                   (event_id, "package-server", kind, now.isoformat(), payload, now.isoformat()))

    def public(self, row):
        return {k: row[k] for k in ("package_id", "sha256", "size", "uploaded_at", "expires_at", "deleted_at")}

    def upload(self, data, expected_hash):
        if len(data) > self.max_bytes:
            raise HTTPException(413, "Package exceeds upload limit")
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_hash:
            raise HTTPException(422, "ZIP SHA-256 mismatch")
        content_id = validate_package(data)
        self.initialize()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM packages WHERE package_id=?", (content_id,)).fetchone()
            if existing:
                if existing["sha256"] != digest:
                    raise HTTPException(409, "Content UUID already has a different package")
                if self.clock() >= datetime.fromisoformat(existing["expires_at"]):
                    raise HTTPException(410, "Package expired; use a new content UUID")
                return {**self.public(existing), "new": False}
            name = uuid.uuid4().hex + ".zip"
            target = self.file_path(name)
            try:
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                # Retention begins only after validation and the complete file write.
                now = self.clock()
                expires = now + RETENTION
                db.execute("INSERT INTO packages VALUES (?,?,?,?,?,?,NULL)",
                           (content_id, digest, len(data), name, now.isoformat(), expires.isoformat()))
                row = db.execute("SELECT * FROM packages WHERE package_id=?", (content_id,)).fetchone()
                self.event(db, row, "PACKAGE_UPLOAD_SUCCESS", now)
                db.commit()
            except BaseException:
                with suppress(OSError):
                    target.unlink(missing_ok=True)
                raise
            return {**self.public(row), "new": True}

    def list(self, limit):
        self.initialize()
        with closing(self.connect()) as db:
            rows = db.execute("SELECT * FROM packages ORDER BY uploaded_at DESC LIMIT ?", (limit,)).fetchall()
        return [self.public(row) for row in rows]

    def download(self, package_id, kind="zip", image_index=0):
        self.initialize()
        # Serializes with cleanup; returning bounded bytes avoids file-open/unlink races.
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM packages WHERE package_id=?", (str(package_id),)).fetchone()
            if not row:
                raise HTTPException(404, "Package not found")
            if row["deleted_at"] or self.clock() >= datetime.fromisoformat(row["expires_at"]):
                raise HTTPException(410, "Package expired")
            try:
                with self.file_path(row["filename"]).open("rb") as source:
                    data = source.read(self.max_bytes + 1)
            except (OSError, RuntimeError) as exc:
                raise HTTPException(503, "Package file unavailable") from exc
            if len(data) != row["size"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise HTTPException(503, "Stored package integrity check failed")
            name = str(package_id) + ".zip"
            if kind != "zip":
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    names = {"html": "index.html", "txt": "article.txt", "docx": "article.docx",
                             "manifest": "manifest.json"}
                    if kind == "image":
                        images = json.loads(archive.read("manifest.json"))["image_order"]
                        if image_index >= len(images):
                            raise HTTPException(404, "Image not found")
                        name = images[image_index]
                    else:
                        name = names[kind]
                    data = archive.read(name)
            if self.clock() >= datetime.fromisoformat(row["expires_at"]):
                raise HTTPException(410, "Package expired")
            db.execute("INSERT INTO package_downloads(package_id,kind,downloaded_at) VALUES (?,?,?)",
                       (str(package_id), kind, self.clock().isoformat()))
            return data, hashlib.sha256(data).hexdigest(), Path(name).name

    def maintain(self):
        self.initialize()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now = self.clock()
            rows = db.execute("SELECT * FROM packages WHERE deleted_at IS NULL").fetchall()
            for row in rows:
                remaining = datetime.fromisoformat(row["expires_at"]) - now
                if remaining <= timedelta(0):
                    try:
                        self.file_path(row["filename"]).unlink(missing_ok=True)
                    except (OSError, RuntimeError):
                        LOG.exception("Package deletion failed: %s", row["package_id"])
                        continue
                    db.execute("UPDATE packages SET deleted_at=? WHERE package_id=?",
                               (now.isoformat(), row["package_id"]))
                    self.event(db, row, "PACKAGE_DELETED", now)
                else:
                    # Catch up missed thresholds after a restart, but never warn after expiry.
                    for hours in (6, 1):
                        if remaining <= timedelta(hours=hours):
                            self.event(db, row, f"PACKAGE_EXPIRING_{hours}H", now)
            referenced = {r[0] for r in db.execute("SELECT filename FROM packages")}
            # Crash before metadata commit can leave a private orphan. Never follow links.
            for path in self.root.glob("*.zip"):
                if STORED.fullmatch(path.name) and path.name not in referenced:
                    try:
                        self.file_path(path.name).unlink(missing_ok=True)
                    except (OSError, RuntimeError):
                        LOG.exception("Orphan package deletion failed")

    async def maintenance_loop(self, interval, stop):
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.maintain)
            except Exception:
                LOG.exception("Package maintenance failed; retrying next interval")
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass


def install_routes(application, store, auth, upload_auth=None):
    @application.post("/api/v1/packages", dependencies=[Depends(upload_auth or auth)])
    async def upload(request: Request, x_content_sha256: str = Header(...)):
        if not re.fullmatch(r"[0-9a-f]{64}", x_content_sha256):
            raise HTTPException(422, "Expected lowercase SHA-256")
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/zip":
            raise HTTPException(415, "Expected application/zip")
        length = request.headers.get("content-length")
        if length is not None:
            if not length.isdecimal():
                raise HTTPException(400, "Invalid Content-Length")
            if int(length) > store.max_bytes:
                raise HTTPException(413, "Package exceeds upload limit")
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > store.max_bytes:
                raise HTTPException(413, "Package exceeds upload limit")
            data.extend(chunk)
        return await asyncio.to_thread(store.upload, data, x_content_sha256)

    @application.get("/api/v1/packages", dependencies=[Depends(auth)])
    def packages():
        return store.list(100)

    @application.get("/api/v1/packages/{package_id}/download", dependencies=[Depends(auth)])
    def download(package_id: uuid.UUID,
                 kind: Literal["zip", "html", "txt", "docx", "manifest", "image"] = "zip",
                 image_index: int = Query(0, ge=0, le=29)):
        data, digest, name = store.download(package_id, kind, image_index)
        return Response(data, media_type="application/zip" if kind == "zip" else "application/octet-stream", headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Content-SHA256": digest, "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})
