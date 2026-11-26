"""Server origin policy and actionable, secret-free connection failures."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "windows-app"))
from send_mock_event import validate_url
from blog_gui.services import Services, ServiceError, safe_error
from blog_gui.storage import Settings, Store


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000", "http://localhost:18000", "http://[::1]:8000", "https://blog.example.com", "https://blog.example.com:8443", "https://61.105.141.21:10443"])
def test_valid_origins(url):
    assert validate_url(" " + url + "/ ") == url


@pytest.mark.parametrize("url", ["http://192.168.0.2:8000", "https://host:0", "https://host:65536", "https://host:abc", "https://host:", "https://host/api/v1", "https://user:SECRET@host", "https://host?token=SECRET", "https://host/#secret", "https://ho\nst", "https://host\\evil", "https://[::1"])
def test_invalid_origins(url):
    with pytest.raises(ValueError) as caught:
        validate_url(url)
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize("detail, expected", [("[SSL: WRONG_VERSION_NUMBER] SECRET", "HTTP 포트"), ("CERTIFICATE_VERIFY_FAILED SECRET", "인증서 검증"), ("Connection refused SECRET", "HTTPS 포트")])
def test_connect_errors_are_actionable_and_redacted(detail, expected):
    error = httpx.ConnectError("connection failed SECRET")
    error.__cause__ = OSError(detail)
    message = safe_error(error)
    assert expected in message
    assert "SECRET" not in message


@pytest.mark.parametrize("status, expected", [(308, "최종 HTTPS"), (502, "내부 포트"), (401, "401")])
def test_http_failure_guidance(status, expected):
    response = httpx.Response(status, request=httpx.Request("GET", "https://host"), text="SECRET", headers={"Location": "https://evil/SECRET"})
    with pytest.raises(httpx.HTTPStatusError) as caught:
        response.raise_for_status()
    assert expected in safe_error(caught.value)
    assert "SECRET" not in safe_error(caught.value)


def test_connect_does_not_forward_token_on_redirect(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(308, headers={"Location": "https://other.example.com"})
    service = Services(Store(tmp_path), lambda: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False))
    with pytest.raises(ServiceError):
        service.connect(Settings(server_url="https://blog.example.com"), "SECRET")
    assert len(requests) == 1
    assert "X-Device-Token" not in requests[0].headers


def test_real_tls_connection_and_untrusted_certificate(tmp_path):
    import json
    import shutil
    import ssl
    import subprocess
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    openssl = shutil.which("openssl")
    if not openssl:
        bundled = Path("C:/Program Files/Git/usr/bin/openssl.exe")
        if bundled.exists():
            openssl = str(bundled)
    if not openssl:
        pytest.skip("OpenSSL executable required for real TLS regression")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1",
                    "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/v1/health":
                status, body = 200, {"status": "ok"}
            elif self.headers.get("X-Device-Token") == "tls-test-token":
                status, body = 200, []
            else:
                status, body = 401, {}
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        settings = Settings(server_url=f"https://127.0.0.1:{server.server_port}")
        store = Store(tmp_path / "store")
        # Trust only this test certificate; certificate verification stays enabled.
        trusted = ssl.create_default_context(cafile=str(cert))
        service = Services(store, lambda: httpx.Client(verify=trusted, trust_env=False, timeout=5))
        assert service.connect(settings, "tls-test-token") == []
        with pytest.raises(ServiceError):
            service.connect(settings, "wrong-token")
        untrusted = Services(store, lambda: httpx.Client(trust_env=False, timeout=5))
        with pytest.raises(ServiceError) as caught:
            untrusted.connect(settings, "tls-test-token")
        assert "인증서 검증" in safe_error(caught.value)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
