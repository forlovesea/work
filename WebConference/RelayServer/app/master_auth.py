"""Master password hashes and short-lived, revocable management sessions."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import time

from fastapi import HTTPException

ITERATIONS = 600_000
SESSION_SECONDS = 3600


def default_key_path():
    return Path(os.getenv("MASTER_KEY_FILE") or (
        "/etc/moa/master-key.json" if os.name == "posix" else
        str(Path(__file__).resolve().parents[1] / "data" / "master-key.json")))


def make_key(password):
    if not 12 <= len(password) <= 256:
        raise ValueError("Master 키는 12~256자로 입력하세요.")
    salt = secrets.token_bytes(32)
    return {"version": 1, "algorithm": "pbkdf2-sha256", "iterations": ITERATIONS,
            "salt": salt.hex(), "hash": hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex(),
            "revision": secrets.token_hex(32)}


def write_key(path, password, *, service_owner=False):
    record = make_key(password)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".master-key-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(record, out)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, 0o640)
        if os.name == "posix" and service_owner:
            import grp
            # Fail rather than install a key the moa service cannot read.
            os.chown(temporary, 0, grp.getgrnam("moa").gr_gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class MasterAuth:
    def __init__(self, db, path=None):
        self.db, self.path = db, Path(path) if path else default_key_path()
        self.sessions = {}
        self.revision = (self.record() or {}).get("revision")
        self.verify_slots = asyncio.Semaphore(2)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS master_login_attempts (at REAL, ip_hash TEXT);
            CREATE INDEX IF NOT EXISTS master_login_attempts_at ON master_login_attempts(at);
            CREATE TABLE IF NOT EXISTS master_audit (
                at REAL, action TEXT, room_id TEXT, participant_id TEXT
            );
        """)

    def record(self):
        try:
            if self.path.stat().st_size > 4096:
                return None
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (data["version"] != 1 or data["algorithm"] != "pbkdf2-sha256" or data["iterations"] != ITERATIONS
                    or len(bytes.fromhex(data["salt"])) != 32 or len(bytes.fromhex(data["hash"])) != 32
                    or len(bytes.fromhex(data["revision"])) != 32):
                return None
            return data
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @property
    def available(self):
        return self.record() is not None

    def limit(self, ip):
        now = time.time()
        key = hashlib.sha256(ip.encode()).hexdigest()
        self.db.execute("DELETE FROM master_login_attempts WHERE at<?", (now - 600,))
        rows = self.db.execute("SELECT ip_hash FROM master_login_attempts").fetchall()
        if len(rows) >= 30 or sum(r["ip_hash"] == key for r in rows) >= 5:
            self.db.commit()
            raise HTTPException(429, "Master 인증 시도가 너무 많습니다. 10분 후 다시 시도하세요.")
        self.db.execute("INSERT INTO master_login_attempts VALUES (?,?)", (now, key))
        self.db.commit()

    async def login(self, password, ip):
        record = self.record()
        if not record:
            raise HTTPException(503, "Master 키가 등록되지 않았습니다. 서버에서 키 설정 명령을 실행하세요.")
        if record["revision"] != self.revision:
            self.sessions.clear()
            self.db.execute("DELETE FROM master_login_attempts")
            self.db.commit()
            self.revision = record["revision"]
        self.limit(ip)
        async with self.verify_slots:
            actual = await asyncio.to_thread(hashlib.pbkdf2_hmac, "sha256", password.encode(),
                                             bytes.fromhex(record["salt"]), ITERATIONS)
        current = self.record()
        if (not current or current["revision"] != record["revision"] or
                not secrets.compare_digest(actual.hex(), record["hash"])):
            raise HTTPException(401, "Master 키가 올바르지 않습니다.")
        now = time.time()
        self.sessions = {k: v for k, v in self.sessions.items() if v["expires_at"] > now and v["revision"] == current["revision"]}
        token = secrets.token_urlsafe(48)
        self.sessions[self.token_hash(token)] = {"expires_at": now + SESSION_SECONDS, "revision": current["revision"]}
        self.audit("login")
        return {"token": token, "expires_at": now + SESSION_SECONDS}

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def require(self, authorization):
        token = authorization.removeprefix("Bearer ")
        if not token or len(token) > 200:
            raise HTTPException(401, "Master 인증이 필요합니다.")
        key = self.token_hash(token)
        session = self.sessions.get(key)
        record = self.record()
        if not session or not record or session["expires_at"] <= time.time() or session["revision"] != record["revision"]:
            self.sessions.pop(key, None)
            raise HTTPException(401, "Master 인증이 만료되었거나 해제되었습니다. 다시 인증하세요.")
        return {"expires_at": session["expires_at"]}

    def logout(self, authorization):
        self.sessions.pop(self.token_hash(authorization.removeprefix("Bearer ")), None)

    def audit(self, action, room_id="", participant_id=""):
        self.db.execute("INSERT INTO master_audit VALUES (?,?,?,?)", (time.time(), action, room_id, participant_id))
        self.db.commit()
