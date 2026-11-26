import json
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "windows-app"))
from blog_gui.chatgpt import AUTH, API, SCOPES, ChatGPT, ChatGPTError
from blog_gui.services import Services, ServiceError, safe_error
from blog_gui.storage import Store, Settings
from blog_gui.workflow import author_locally


class MemoryVault:
    def __init__(self):
        self.values = {}

    def get(self, name):
        return self.values.get(name, "")

    def set(self, name, value):
        self.values[name] = value


def connected(tmp_path, handler=None, expires=3600):
    factory = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    client = ChatGPT(Store(tmp_path), MemoryVault(), factory)
    client.save({"active": "oaiapp_test", "accounts": {"oaiapp_test": {
        "subject": "user", "email": "test@example.com", "scope": SCOPES,
        "access_token": "ACCESS_SECRET", "refresh_token": "REFRESH_SECRET",
        "expires_at": time.time() + expires}}})
    return client


@pytest.mark.parametrize("problem", [None, "nonce", "signature", "scope", "client", "denied"])
def test_oauth_pkce_and_identity_validation(tmp_path, problem):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk["kid"] = "key1"
    captured = {}
    def opener(url):
        query = parse_qs(urlsplit(url).query)
        captured.update({k: v[0] for k, v in query.items()})
        assert captured["client_id"] == "dynamic_agent_client"
        assert captured["ext_agent_host_id"].startswith("urn:uuid:")
        def callback():
            with httpx.Client(trust_env=False) as browser:
                # An unrelated request cannot complete the login.
                assert browser.get(captured["redirect_uri"] + "?state=wrong&code=bad").status_code == 400
                params = {"state": captured["state"], "code": "CODE", "client_id": "oaiapp_test"}
                if problem == "client":
                    params.pop("client_id")
                if problem == "denied":
                    params["error"] = "access_denied"
                browser.get(captured["redirect_uri"] + "?" + urlencode(params))
        threading.Thread(target=callback, daemon=True).start()
        return True
    def handler(request):
        if request.url.path.endswith("jwks.json"):
            return httpx.Response(200, json={"keys": [jwk]})
        body = parse_qs(request.content.decode())
        assert body["client_id"] == ["oaiapp_test"]
        assert body["redirect_uri"] == [captured["redirect_uri"]]
        import hashlib, base64
        assert base64.urlsafe_b64encode(hashlib.sha256(body["code_verifier"][0].encode()).digest()).rstrip(b"=").decode() == captured["code_challenge"]
        claims = {"sub": "user", "iss": AUTH, "aud": "oaiapp_test", "iat": time.time(),
                  "exp": time.time() + 300, "nonce": "wrong" if problem == "nonce" else captured["nonce"]}
        signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if problem == "signature" else private
        token = jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "key1"})
        return httpx.Response(200, json={"id_token": token, "access_token": "ACCESS_SECRET", "refresh_token": "REFRESH_SECRET",
            "scope": "openid" if problem == "scope" else SCOPES, "expires_in": 3600, "token_type": "Bearer"})
    client = ChatGPT(Store(tmp_path), MemoryVault(), lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    if problem:
        with pytest.raises(ChatGPTError):
            client.login(opener=opener, timeout=5)
        assert not client.connected()
    else:
        client.login(opener=opener, timeout=5)
        assert client.connected()
        assert b"ACCESS_SECRET" not in client.path.read_bytes()
        assert "REFRESH_SECRET" not in client.store.path.read_bytes().decode(errors="ignore")


def test_refresh_rotation_and_account_model_catalog(tmp_path):
    def handler(request):
        if request.url.path.endswith("/token"):
            data = parse_qs(request.content.decode())
            assert data["refresh_token"] == ["REFRESH_SECRET"]
            assert data["client_id"] == ["oaiapp_test"]
            assert "scope" not in data
            return httpx.Response(200, json={"access_token": "NEW", "refresh_token": "ROTATED", "token_type": "Bearer", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer NEW"
        return httpx.Response(200, json={"models": [{"slug": "available", "display_name": "Available", "visibility": "list"}, {"slug": "hidden", "visibility": "hide"}]})
    client = connected(tmp_path, handler, expires=-1)
    assert client.models() == [("available", "Available")]
    assert client.records()["accounts"]["oaiapp_test"]["refresh_token"] == "ROTATED"


@pytest.mark.parametrize("completion", [True, False])
def test_subscription_stream_and_no_api_fallback(tmp_path, completion):
    content = {"title_candidates": ["a", "b", "c"], "title": "t", "summary": "s", "sections": [{"heading": "h", "body": "b"}], "tags": [], "seo_keywords": []}
    def handler(request):
        assert str(request.url) == API + "/responses"
        assert request.headers["Authorization"] == "Bearer ACCESS_SECRET"
        payload = json.loads(request.content)
        assert payload["store"] is False and payload["stream"] is True
        assert isinstance(payload["input"], list) and "max_output_tokens" not in payload
        data = {"type": "response.completed", "response": {"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps(content)}]}]}}
        return httpx.Response(200, text=("data: " + json.dumps(data) + "\n\n") if completion else "data: [DONE]\n\n")
    client = connected(tmp_path, handler)
    services = Services(client.store)
    services.chatgpt = client
    config = Settings(mock=False, writer_provider="chatgpt", chatgpt_model="available")
    if completion:
        result = author_locally(services, config, "NEVER_USE_API_KEY")
        assert not result["article"]["mock"] and Path(result["path"]).exists()
    else:
        with pytest.raises(ChatGPTError, match="끊겼"):
            services.write_article(config, "NEVER_USE_API_KEY", "topic")
        assert not client.store.articles()
    with pytest.raises(ServiceError, match="지원하지"):
        services.generate_image(config, "NEVER_USE_API_KEY", "topic")


def test_quota_redaction_and_no_paid_fallback(tmp_path):
    client = connected(tmp_path, lambda request: httpx.Response(429, text="SECRET"))
    with pytest.raises(ChatGPTError) as exc:
        client.respond("model", "instructions", "prompt")
    assert "한도" in safe_error(exc.value) and "SECRET" not in safe_error(exc.value)


def test_logout_preserves_mapping_and_clears_tokens(tmp_path):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"revocation_endpoint": AUTH + "/revoke"})
        assert parse_qs(request.content.decode())["token"] == ["REFRESH_SECRET"]
        return httpx.Response(200)
    client = connected(tmp_path, handler)
    assert client.logout() == "로그아웃 완료"
    assert not client.connected()
    assert client.records()["accounts"]["oaiapp_test"]["subject"] == "user"


def test_subscription_image_preflight_does_not_consume_text(tmp_path):
    services = Services(Store(tmp_path))
    with pytest.raises(ServiceError, match="이미지"):
        author_locally(services, Settings(mock=False, writer_provider="chatgpt", scheduled_image=True), "")
    assert not services.store.articles()
