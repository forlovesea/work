"""Local settings guidance; never prints credentials or probes another endpoint."""
import ipaddress
from urllib.parse import urlsplit
from send_mock_event import validate_url


def settings_report(url, mock, has_key, has_token, provider="openai", chatgpt_connected=False):
    lines = ["현재 입력값 진단 · 변경한 값은 설정 저장 후 작업에 적용됩니다."]
    if provider == "chatgpt":
        lines.append("AI: ChatGPT 구독 연결 · " + ("로그인됨" if chatgpt_connected else "Continue with ChatGPT 로그인 필요") +
                     (" · Mock 모드 ON: 테스트 글만 생성합니다." if mock else " · 실제 글쓰기: 모델 선택 후 설정을 저장하세요.") +
                     " API 키는 필요하지 않으며 API 과금으로 자동 전환하지 않습니다.")
    elif mock:
        lines.append("AI: Mock 모드 ON → 테스트 글/이미지만 생성합니다. 실제 AI는 키 저장 후 Mock을 해제하세요.")
    elif not has_key:
        lines.append("AI: 실제 모드지만 API 키가 없습니다. OpenAI API 키 입력 → 설정 저장이 필요합니다.")
    else:
        lines.append("AI: 실제 모드 · 키 있음. 키 유효성/모델 권한은 실제 요청 시 확인됩니다.")
    lines.append("서버 토큰: " + ("있음 · 서버와 일치하는지는 연결 시 확인합니다." if has_token else "없음 · 서버 인증에는 필요하지만 AI 글쓰기에는 필요 없습니다."))
    try:
        parsed = urlsplit(validate_url(url))
    except ValueError as exc:
        lines.append("서버 주소: " + str(exc))
        return "\n\n".join(lines)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    lines.append(f"접속 대상: {parsed.hostname} / {parsed.scheme.upper()} / 포트 {port}")
    if parsed.scheme == "https":
        lines.append(f"이 주소는 {port} 포트에서 실제 TLS를 제공해야 합니다. 주소 앞에 https를 붙이는 것만으로 HTTPS가 켜지지 않습니다.")
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            pass
        else:
            lines.append("IP 주소 접속: 인증서에 이 IP가 포함돼야 합니다. 도메인용 인증서라면 해당 도메인으로 접속하세요.")
    else:
        lines.append("로컬 HTTP: 이 Windows PC의 서버 또는 실행 중인 SSH 터널인지 확인하세요.")
    lines.append("서버가 오프라인이어도 AI 글쓰기와 로컬 파일 저장은 사용할 수 있습니다.")
    return "\n\n".join(lines)
