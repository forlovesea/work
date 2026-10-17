"""Single-use Master email approval for room creation. No secrets in URLs/logs."""
import asyncio
import hashlib
import logging
import os
import re
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from urllib.parse import urlsplit

from fastapi import HTTPException

MASTER_EMAIL = "forlovesea@gmail.com"
TTL = 30 * 60
log = logging.getLogger(__name__)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def identity(name, contact):
    name, contact = name.strip(), contact.strip()
    if not name or len(name) > 40 or re.search(r"[\x00-\x1f\x7f]", name + contact):
        raise HTTPException(422, "이름과 연락처를 올바르게 입력하세요.")
    if not (re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", contact) or
            (re.fullmatch(r"\+?[0-9 ()-]{7,30}", contact) and len(re.sub(r"\D", "", contact)) >= 7)):
        raise HTTPException(422, "연락 가능한 이메일 주소 또는 전화번호를 입력하세요.")
    if len(contact) > 120:
        raise HTTPException(422, "연락처가 너무 깁니다.")
    return name, contact


class ApprovalService:
    def __init__(self, db, *, required=True, sender=None):
        self.db, self.required, self.sender = db, required, sender
        self.base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
        self.host = os.getenv("SMTP_HOST", "")
        try:
            self.port = int(os.getenv("SMTP_PORT", "587"))
        except ValueError:
            self.port = 0
        self.security = os.getenv("SMTP_SECURITY", "starttls")
        self.user = os.getenv("SMTP_USERNAME", "")
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.from_address = os.getenv("SMTP_FROM", self.user)
        try:
            base = urlsplit(self.base_url)
        except ValueError:
            base = urlsplit("")
        self.ready = sender is not None or bool(
            self.host and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.from_address) and 1 <= self.port <= 65535
            and base.scheme == "https" and base.netloc and not base.username and not base.password
            and not base.query and not base.fragment and base.path in ("", "/")
            and self.security in ("ssl", "starttls") and bool(self.user) == bool(self.password))
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS host_approvals (
                id TEXT PRIMARY KEY, client_hash TEXT NOT NULL, master_hash TEXT NOT NULL,
                name TEXT NOT NULL, contact TEXT NOT NULL, status TEXT NOT NULL,
                created REAL NOT NULL, expires REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approval_attempts (
                at REAL NOT NULL, ip_hash TEXT NOT NULL, contact_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS approval_attempts_time ON approval_attempts(at);
        """)
        self.prune()

    def prune(self):
        now = time.time()
        self.db.execute("DELETE FROM host_approvals WHERE expires < ?", (now - 86400,))
        self.db.execute("DELETE FROM approval_attempts WHERE at < ?", (now - 3600,))
        self.db.commit()

    def limit(self, ip, contact):
        self.prune()
        now = time.time()
        contact_key = digest(re.sub(r"[ ()-]", "", contact.lower()))
        ip_key = digest(ip)
        rows = self.db.execute("SELECT at, ip_hash, contact_hash FROM approval_attempts").fetchall()
        if (len(rows) >= 20 or sum(r["ip_hash"] == ip_key for r in rows) >= 5
                or sum(r["contact_hash"] == contact_key for r in rows) >= 3
                or any(r["contact_hash"] == contact_key and r["at"] > now - 60 for r in rows)):
            raise HTTPException(429, "인증 요청이 너무 많습니다. 잠시 후 다시 시도하세요.")
        self.db.execute("INSERT INTO approval_attempts VALUES (?,?,?)", (now, ip_key, contact_key))
        self.db.commit()

    def send_mail(self, name, contact, link):
        if self.sender is not None:
            self.sender(name, contact, link)
            return
        message = EmailMessage()
        message["Subject"] = "[모아] 새 회의 생성 승인 요청"
        message["From"] = self.from_address
        message["To"] = MASTER_EMAIL
        message.set_content(
            f"새 회의를 만들려는 사용자가 Master 인증을 요청했습니다.\n\n"
            f"방장 이름: {name}\n연락처: {contact}\n\n"
            f"아래 링크에서 사용자 정보를 확인한 뒤 '인증완료' 또는 '거절'을 눌러 주세요.\n{link}\n\n"
            "링크는 30분 동안 유효합니다. 링크를 여는 것만으로는 승인되지 않습니다.\n"
            "이 링크를 가진 사람은 승인할 수 있으므로 다른 사람에게 전달하지 마세요.\n"
            "승인은 해당 이름과 연락처로 새 회의 1회를 만드는 데 사용됩니다.\n")
        context = ssl.create_default_context()
        if self.security == "ssl":
            connection = smtplib.SMTP_SSL(self.host, self.port, timeout=15, context=context)
        else:
            connection = smtplib.SMTP(self.host, self.port, timeout=15)
        with connection as smtp:
            if self.security == "starttls":
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(message, to_addrs=[MASTER_EMAIL])

    async def request(self, name, contact, ip):
        if not self.ready:
            raise HTTPException(503, "Master 이메일 발송 설정이 준비되지 않았습니다. 서버 관리자에게 문의하세요.")
        name, contact = identity(name, contact)
        self.limit(ip, contact)
        rid, client, master = secrets.token_urlsafe(24), secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        self.db.execute("INSERT INTO host_approvals VALUES (?,?,?,?,?,?,?,?)",
                        (rid, digest(client), digest(master), name, contact, "sending", now, now + TTL))
        self.db.commit()
        # Fragment credentials stay out of HTTP access logs and referrer URLs.
        link = f"{self.base_url}/master-approval#request={rid}&token={master}"
        try:
            await asyncio.to_thread(self.send_mail, name, contact, link)
        except Exception as exc:
            self.db.execute("UPDATE host_approvals SET status='failed' WHERE id=?", (rid,))
            self.db.commit()
            log.warning("Master email delivery failed: %s", type(exc).__name__)
            raise HTTPException(503, "인증 메일을 보내지 못했습니다. 관리자에게 이메일 설정 확인을 요청하세요.") from None
        self.db.execute("UPDATE host_approvals SET status='pending' WHERE id=?", (rid,))
        self.db.commit()
        return {"request_id": rid, "client_token": client, "status": "pending", "expires_at": now + TTL}

    def find(self, rid, token, *, master=False):
        if not token or len(token) > 200:
            raise HTTPException(403, "인증 링크 또는 요청 정보가 올바르지 않습니다.")
        row = self.db.execute("SELECT * FROM host_approvals WHERE id=?", (rid,)).fetchone()
        if row is None or not secrets.compare_digest(row["master_hash" if master else "client_hash"], digest(token)):
            raise HTTPException(403, "인증 링크 또는 요청 정보가 올바르지 않습니다.")
        return row

    def status(self, rid, token, *, master=False):
        row = self.find(rid, token, master=master)
        status = "expired" if row["expires"] < time.time() else row["status"]
        result = {"status": status, "expires_at": row["expires"]}
        if master:
            result.update(name=row["name"], contact=row["contact"], created_at=row["created"])
        return result

    def decide(self, rid, token, decision):
        row = self.find(rid, token, master=True)
        if row["expires"] < time.time():
            raise HTTPException(410, "인증 요청이 만료되었습니다. 사용자에게 다시 요청하도록 안내하세요.")
        target = "approved" if decision == "approve" else "rejected"
        if row["status"] == target:
            return {"status": target, "expires_at": row["expires"]}
        if row["status"] != "pending":
            raise HTTPException(409, "이미 처리되었거나 승인할 수 없는 요청입니다.")
        expires = time.time() + TTL
        self.db.execute("UPDATE host_approvals SET status=?, expires=? WHERE id=?", (target, expires, rid))
        self.db.commit()
        return {"status": target, "expires_at": expires}

    def consume(self, rid, token, name, contact):
        if not self.required:
            return
        row = self.find(rid, token)
        name, contact = identity(name, contact)
        if row["name"] != name or row["contact"] != contact:
            raise HTTPException(403, "승인된 이름과 연락처가 다릅니다. 다시 인증을 요청하세요.")
        result = self.db.execute("UPDATE host_approvals SET status='used' WHERE id=? AND status='approved' AND expires>=?",
                                 (rid, time.time()))
        if result.rowcount != 1:
            self.db.rollback()
            raise HTTPException(403, "Master 인증이 필요합니다. 미승인·만료·사용된 요청으로는 회의를 만들 수 없습니다.")
        # Caller commits this update together with insertion of the new room.
