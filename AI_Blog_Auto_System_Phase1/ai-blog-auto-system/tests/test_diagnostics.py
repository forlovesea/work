import sys
from pathlib import Path
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'windows-app'))
from blog_gui.diagnostics import settings_report
from blog_gui.services import Services, ServiceError
from blog_gui.storage import Settings, Store


def test_screenshot_settings_guidance():
    report = settings_report('https://61.105.141.21:8001', True, False, True)
    assert 'Mock 모드 ON' in report and '8001' in report and 'IP 주소' in report
    assert '서버와 일치하는지' in report
    assert 'API 키가 없습니다' in settings_report('https://example.com', False, False, True)


def test_diagnostics_do_not_echo_url_credentials():
    assert 'SECRET' not in settings_report('https://user:SECRET@example.com', False, False, False)


def test_existing_https_without_blog_route_is_actionable(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(404, json={'detail': 'Not Found'})
    service = Services(Store(tmp_path), lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ServiceError, match='8001'):
        service.connect(Settings(server_url='https://61.105.141.21:10443'), 'SECRET')
    assert len(requests) == 1
    assert 'X-Device-Token' not in requests[0].headers


def test_shared_https_routes_and_auth(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.url.scheme == 'https' and request.url.port == 10443
        if request.url.path == '/api/v1/health':
            assert 'X-Device-Token' not in request.headers
            return httpx.Response(200, json={'status': 'ok'})
        assert request.url.path == '/api/v1/events'
        assert request.headers['X-Device-Token'] == 'test-token'
        return httpx.Response(200, json=[])
    service = Services(Store(tmp_path), lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    assert service.connect(Settings(server_url='https://61.105.141.21:10443'), 'test-token') == []
    assert len(requests) == 2


def test_real_mode_never_silently_becomes_mock(tmp_path):
    service = Services(Store(tmp_path))
    for action in (service.write_article, service.generate_image):
        with pytest.raises(ServiceError, match='API 키'):
            action(Settings(mock=False), '', 'topic')
    assert service.store.articles() == []


@pytest.mark.parametrize('health, expected', [(False, '1/2'), (True, '2/2')])
def test_server_failure_phase_and_redaction(tmp_path, health, expected):
    calls = []
    def handler(request):
        calls.append(request)
        if not health:
            raise httpx.ConnectError('SECRET connection refused', request=request)
        if request.url.path.endswith('health'):
            return httpx.Response(200, json={'status': 'ok'})
        return httpx.Response(401, text='SECRET')
    service = Services(Store(tmp_path), lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ServiceError) as caught:
        service.connect(Settings(server_url='https://example.com:8001'), 'SECRET')
    assert expected in str(caught.value) and '8001' in str(caught.value)
    assert 'SECRET' not in str(caught.value)
    assert 'X-Device-Token' not in calls[0].headers
