"""Official ChatGPT plan OAuth for locally hosted clients. No browser cookies."""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
import webbrowser
from functools import wraps
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
from cryptography.fernet import Fernet

from .storage import Vault

AUTH = "https://auth.openai.com"
API = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
_LOCK = threading.RLock()


class ChatGPTError(Exception):
    pass


def network_errors(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except httpx.HTTPError:
            raise ChatGPTError("ChatGPT 네트워크 연결에 실패했습니다. 인터넷·프록시·PC 시간·TLS 인증서를 확인하고 다시 시도하세요. Ubuntu 서버 연결과는 별개입니다.") from None
    return wrapped


class ChatGPT:
    def __init__(self, store, vault=None, client_factory=None):
        self.store = store
        self.vault = vault or Vault()
        self.client_factory = client_factory or (lambda: httpx.Client(timeout=120, follow_redirects=False))
        self.path = store.directory / "chatgpt-credentials.enc"

    @contextmanager
    def locked(self):
        # Serialize rotating refresh tokens across windows/processes.
        import msvcrt
        with _LOCK, open(self.store.directory / "chatgpt.lock", "a+b") as lock:
            lock.seek(0)
            if not lock.read(1):
                lock.write(b"0")
                lock.flush()
            deadline = time.monotonic() + 15
            while True:
                try:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise ChatGPTError("다른 창에서 ChatGPT 연결을 갱신 중입니다. 잠시 후 다시 시도하세요.") from None
                    time.sleep(.1)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

    def _cipher(self):
        key = self.vault.get("chatgpt-encryption")
        if not key:
            if self.path.exists():
                raise ChatGPTError("ChatGPT 자격 증명을 복호화할 수 없습니다. 원래 Windows 계정으로 실행하세요.")
            key = Fernet.generate_key().decode()
            self.vault.set("chatgpt-encryption", key)
        return Fernet(key.encode())

    def records(self):
        if not self.path.exists():
            return {"accounts": {}, "active": ""}
        try:
            return json.loads(self._cipher().decrypt(self.path.read_bytes()))
        except ChatGPTError:
            raise
        except Exception:
            raise ChatGPTError("ChatGPT 연결 정보를 읽을 수 없습니다. Windows 계정과 저장소를 확인하세요.") from None

    def save(self, records):
        encrypted = self._cipher().encrypt(json.dumps(records).encode())
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(encrypted)
        os.replace(temporary, self.path)

    def accounts(self):
        records = self.records()
        return [(key, value.get("email", "ChatGPT") + " · " + key[-8:])
                for key, value in records["accounts"].items()], records["active"]

    def connected(self):
        records = self.records()
        return bool(records["accounts"].get(records["active"], {}).get("access_token"))

    def select(self, client_id):
        with self.locked():
            records = self.records()
            if client_id not in records["accounts"]:
                raise ChatGPTError("저장된 ChatGPT 계정을 선택하세요.")
            records["active"] = client_id
            self.save(records)

    @staticmethod
    def check(response):
        if response.is_success:
            return response.json()
        hints = {401: "로그인이 만료되었습니다. 다시 로그인하세요.",
                 403: "ChatGPT 구독 사용 권한 또는 계정의 연동 지원 여부를 확인하세요.",
                 429: "ChatGPT 사용 한도에 도달했습니다. ChatGPT 설정의 사용량을 확인하고 나중에 재시도하세요."}
        raise ChatGPTError(f"ChatGPT 요청 실패 (HTTP {response.status_code}). " +
                           hints.get(response.status_code, "잠시 후 다시 시도하거나 계정·모델 권한을 확인하세요."))

    @network_errors
    def login(self, client_id="", opener=webbrowser.open, timeout=180):
        with self.locked():
            records = self.records()
            previous = records["accounts"].get(client_id, {})
            host = self.store.get("chatgpt_host_id")
            if not host:
                host = "urn:uuid:" + str(uuid.uuid4())
                self.store.put("chatgpt_host_id", host)
        state, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
        result = {}

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                valid = (parsed.path == "/auth/callback" and
                         len(query.get("state", [])) == 1 and
                         secrets.compare_digest(query["state"][0], state))
                self.send_response(200 if valid else 400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(("프로그램으로 돌아가 로그인 결과를 확인하세요." if valid else "잘못된 로그인 응답입니다.").encode())
                if valid:
                    result.update(query)

        with HTTPServer(("127.0.0.1", 0), Callback) as server:
            server.timeout = .5
            redirect = f"http://127.0.0.1:{server.server_port}/auth/callback"
            params = dict(client_id=client_id or "dynamic_agent_client", ext_agent_host_id=host,
                          response_type="code", redirect_uri=redirect, scope=SCOPES, resource=API,
                          state=state, nonce=nonce, code_challenge_method="S256",
                          code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode())
            if not client_id:
                params["agent_name_hint"] = "AI Blog Auto System"
            elif previous.get("id_token"):
                params["id_token_hint"] = previous["id_token"]
            if not opener(AUTH + "/api/accounts/authorize?" + urlencode(params)):
                raise ChatGPTError("기본 브라우저를 열 수 없습니다. Windows 기본 브라우저를 설정하세요.")
            deadline = time.monotonic() + timeout
            while not result and time.monotonic() < deadline:
                server.handle_request()
        if not result:
            raise ChatGPTError("로그인 대기 시간이 끝났습니다. 다시 로그인하세요. (3분)")
        if "error" in result:
            raise ChatGPTError("ChatGPT 로그인이 취소되었거나 구독 사용 권한이 승인되지 않았습니다.")
        issued = result.get("client_id", [client_id])[0]
        if not issued or issued == "dynamic_agent_client" or (client_id and issued != client_id):
            raise ChatGPTError("ChatGPT 앱 등록 응답이 올바르지 않습니다.")
        if len(result.get("code", [])) != 1:
            raise ChatGPTError("ChatGPT 로그인 코드가 없습니다.")
        with self.client_factory() as client:
            tokens = self.check(client.post(AUTH + "/api/accounts/oauth/token", data=dict(
                grant_type="authorization_code", client_id=issued, code=result["code"][0],
                code_verifier=verifier, redirect_uri=redirect, resource=API)))
            keys = self.check(client.get(AUTH + "/.well-known/jwks.json"))
        try:
            header = jwt.get_unverified_header(tokens["id_token"])
            key = next(k for k in keys["keys"] if k.get("kid") == header.get("kid"))
            claims = jwt.decode(tokens["id_token"], jwt.PyJWK.from_dict(key).key,
                                algorithms=["RS256"], issuer=AUTH, audience=issued,
                                options={"require": ["exp", "iat", "sub", "nonce"]}, leeway=5)
            if claims["nonce"] != nonce or not claims["sub"] or (previous and claims["sub"] != previous["subject"]):
                raise ValueError()
        except Exception:
            raise ChatGPTError("ChatGPT 로그인 서명 또는 계정 검증에 실패했습니다.") from None
        self.validate_tokens(tokens)
        account = {**tokens, "subject": claims["sub"], "email": claims.get("email", "ChatGPT"),
                   "expires_at": time.time() + float(tokens["expires_in"])}
        with self.locked():
            records = self.records()
            records["accounts"][issued] = account
            records["active"] = issued
            self.save(records)
        return "ChatGPT 로그인 완료. 모델 목록을 불러온 뒤 설정을 저장하세요."

    @staticmethod
    def validate_tokens(tokens):
        if not {"resource.invoke", "chatgpt.tokens.use.direct"}.issubset(tokens.get("scope", "").split()):
            raise ChatGPTError("ChatGPT 구독 사용 권한이 없습니다. 다시 로그인해 구독 사용을 허용하세요.")
        if not tokens.get("access_token") or str(tokens.get("token_type", "")).lower() != "bearer" or float(tokens.get("expires_in", 0)) <= 0:
            raise ChatGPTError("ChatGPT 인증 응답이 불완전합니다. 다시 로그인하세요.")

    def access_token(self):
        with self.locked():
            records = self.records()
            client_id = records["active"]
            account = records["accounts"].get(client_id, {})
            if not account.get("access_token"):
                raise ChatGPTError("설정에서 Continue with ChatGPT로 로그인하세요.")
            if account["expires_at"] < time.time() + 90:
                if not account.get("refresh_token"):
                    raise ChatGPTError("ChatGPT 로그인이 만료되었습니다. 다시 로그인하세요.")
                with self.client_factory() as client:
                    tokens = self.check(client.post(AUTH + "/api/accounts/oauth/token", data=dict(
                        grant_type="refresh_token", client_id=client_id,
                        refresh_token=account["refresh_token"], resource=API)))
                tokens.setdefault("scope", account["scope"])
                self.validate_tokens(tokens)
                account.update(tokens)
                account["expires_at"] = time.time() + float(tokens["expires_in"])
                self.save(records)
            return account["access_token"]

    @network_errors
    def models(self):
        token = self.access_token()
        with self.client_factory() as client:
            data = self.check(client.get(API + "/models", headers={"Authorization": "Bearer " + token}))
        models = [(m["slug"], m.get("display_name", m["slug"])) for m in data.get("models", []) if m.get("visibility") == "list"]
        if not models:
            raise ChatGPTError("이 계정에서 사용할 ChatGPT 모델이 없습니다. 구독과 권한을 확인하세요.")
        return models

    @network_errors
    def respond(self, model, instructions, prompt):
        if not model:
            raise ChatGPTError("설정에서 ChatGPT 모델 목록을 불러와 모델을 선택하고 저장하세요.")
        token = self.access_token()
        with self.client_factory() as client:
            with client.stream("POST", API + "/responses", headers={"Authorization": "Bearer " + token},
                               json={"model": model, "instructions": instructions,
                                     "input": [{"role": "user", "content": prompt}],
                                     "store": False, "stream": True,
                                     "text": {"format": {"type": "json_object"}}}) as response:
                if not response.is_success:
                    response.read()
                    self.check(response)
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    event = json.loads(raw)
                    if event.get("type") == "response.completed":
                        return event["response"]
                    if event.get("type") in {"error", "response.failed", "response.incomplete"}:
                        raise ChatGPTError("ChatGPT 글 생성이 완료되지 않았습니다. 사용량과 모델을 확인하세요.")
        raise ChatGPTError("ChatGPT 응답이 중간에 끊겼습니다. 완성된 글은 저장하지 않았습니다.")

    def logout(self):
        confirmed = False
        with self.locked():
            records = self.records()
            account = records["accounts"].get(records["active"], {})
            try:
                if account.get("refresh_token"):
                    with self.client_factory() as client:
                        discovery = self.check(client.get(AUTH + "/.well-known/openid-configuration"))
                        endpoint = discovery["revocation_endpoint"]
                        parsed = urlsplit(endpoint)
                        if parsed.scheme != "https" or parsed.hostname != "auth.openai.com":
                            raise ValueError()
                        for attempt in range(3):
                            try:
                                response = client.post(endpoint, data={"token": account["refresh_token"],
                                    "token_type_hint": "refresh_token", "client_id": records["active"]})
                                confirmed = response.status_code == 200
                                if response.status_code < 500:
                                    break
                            except httpx.HTTPError:
                                pass
                            time.sleep(.5 * (attempt + 1))
            except Exception:
                pass
            for field in ("access_token", "refresh_token", "id_token"):
                account.pop(field, None)
            self.save(records)
        return "로그아웃 완료" if confirmed else "로컬 로그아웃 완료. 원격 해제는 확인되지 않았습니다. ChatGPT 설정에서 앱 연결을 해제하세요."
