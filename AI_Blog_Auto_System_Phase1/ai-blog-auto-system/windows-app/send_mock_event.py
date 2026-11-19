"""Mock sender with a durable SQLite outbox. No Naver login or publishing."""
import argparse
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.username or parsed.password or parsed.query or parsed.fragment
            or not parsed.hostname or parsed.path not in ("", "/")):
        raise ValueError("Use a server origin without credentials, query or path")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    ):
        raise ValueError("Remote server URLs must use HTTPS with a valid certificate")
    return url.rstrip("/")


class Outbox:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS outbox (event_id TEXT PRIMARY KEY, body TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(str(self.path))

    def enqueue(self, event):
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO outbox VALUES (?,?)", (event["event_id"], json.dumps(event, ensure_ascii=False)))

    def flush(self, client, url, token):
        with closing(self.connect()) as db:
            rows = db.execute("SELECT event_id, body FROM outbox ORDER BY rowid").fetchall()
        sent = 0
        for event_id, body in rows:
            response = client.post(url + "/api/v1/events", headers={"X-Device-Token": token}, json=json.loads(body))
            response.raise_for_status()
            ack = response.json()
            if ack.get("event_id") != event_id or ack.get("accepted") is not True:
                raise ValueError("Invalid acknowledgement; event retained")
            with closing(self.connect()) as db, db:
                db.execute("DELETE FROM outbox WHERE event_id=?", (event_id,))
            sent += 1
        return sent


def mock_event(device_id):
    return {"event_id": str(uuid.uuid4()), "device_id": device_id,
            "event_type": "MOCK_PUBLISH_SUCCESS",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"title": "테스트용 글 (실제 게시 아님)", "status": "MOCK_ONLY"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flush-only", action="store_true", help="Retry pending events without creating another")
    args = parser.parse_args()
    token = os.getenv("BLOG_DEVICE_TOKEN", "")
    if not token:
        parser.error("Set BLOG_DEVICE_TOKEN before running")
    try:
        url = validate_url(os.getenv("BLOG_SERVER_URL", "http://127.0.0.1:8000"))
    except ValueError as exc:
        parser.error(str(exc))
    outbox = Outbox(os.getenv("BLOG_OUTBOX_PATH", "./outbox.sqlite3"))
    if not args.flush_only:
        outbox.enqueue(mock_event(os.getenv("BLOG_DEVICE_ID", "WINDOWS-PC-TEST")))
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            print("Acknowledged events:", outbox.flush(client, url, token))
        return 0
    except (httpx.HTTPError, ValueError):
        # Do not print exception request details or secrets.
        print("Delivery failed. Pending events retained; retry with --flush-only.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
