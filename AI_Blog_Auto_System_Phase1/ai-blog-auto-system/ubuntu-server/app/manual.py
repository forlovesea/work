"""User-reported completion; never a verified Naver publication."""
import json
import uuid
from contextlib import closing
from datetime import datetime
from urllib.parse import urlsplit
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class Completion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: StrictBool
    post_url: str = Field(max_length=2048)

    @field_validator("post_url")
    @classmethod
    def official_url(cls, value):
        p = urlsplit(value)
        if (p.scheme != "https" or p.hostname not in {"blog.naver.com", "m.blog.naver.com"}
                or p.username or p.password or p.port is not None or p.fragment
                or not p.path.strip("/") or any(c.isspace() or ord(c) < 32 for c in value)):
            raise ValueError("Use the HTTPS URL of the manually published Naver blog post")
        return value


def install_manual(app, store, auth):
    @app.post("/api/v1/packages/{package_id}/manual-completion", dependencies=[Depends(auth)])
    def complete(package_id: uuid.UUID, body: Completion):
        if body.confirmed is not True:
            raise HTTPException(422, "Explicit user confirmation is required")
        store.initialize()
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "manual-completion:" + str(package_id)))
        payload = {"package_id": str(package_id), "post_url": body.post_url, "source": "user_report", "verified": False}
        with closing(store.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM packages WHERE package_id=?", (str(package_id),)).fetchone()
            if not row:
                raise HTTPException(404, "Package not found")
            previous = db.execute("SELECT payload FROM events WHERE event_id=?", (event_id,)).fetchone()
            if previous:
                if json.loads(previous[0]) != payload:
                    raise HTTPException(409, "Completion already recorded with another URL")
                return {"event_id": event_id, "new": False, "verified": False}
            now = store.clock()
            if row["deleted_at"] or now >= datetime.fromisoformat(row["expires_at"]):
                raise HTTPException(410, "Package expired")
            db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (event_id, "manual-user", "MANUAL_PUBLISH_COMPLETED",
                now.isoformat(), json.dumps(payload, sort_keys=True), now.isoformat()))
        return {"event_id": event_id, "new": True, "verified": False}
