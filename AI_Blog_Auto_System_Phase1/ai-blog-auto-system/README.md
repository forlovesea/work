# AI Blog Auto System — Windows · Ubuntu 서버 · Android

## 개발 상세서 및 설치·사용법

**[개발 상세서 바로가기](docs/development-guide.md)** — 구조, 구현 범위, 모듈, API, 데이터, 오류 복구, 테스트와 유지보수.

| 프로젝트 | 설치·사용법 |
|---|---|
| Windows EXE / PySide6 | [Windows 설치·사용 가이드](docs/windows-install-use.md) |
| Ubuntu / FastAPI 서버 | [Ubuntu 설치·사용 가이드](docs/ubuntu-install-use.md) |
| Android / Compose | [Android 설치·사용 가이드](docs/android-install-use.md) |

[설치 파일과 SHA-256](release/2026-11-19/README.md) · [통합 시험 결과](docs/integration-test-results.md) · [운영 배포·롤백](docs/build-and-deploy.md)

아래 명령은 개발 환경의 빠른 시작용입니다. 처음 사용하는 경우 위 프로젝트별 가이드 순서대로 진행하세요.

Phase 1 서버/CLI를 유지하면서 PySide6 Windows GUI를 추가했습니다.
Mock 모드에서 API 키 없이 뉴스·글·이미지와 예약 작업을 실행할 수 있습니다.
실제 네이버 로그인 자동 확인·자동 게시는 비활성화되어 있습니다. Windows EXE와 Android APK를 로컬 빌드하며 운영 서버에는 배포하지 않았습니다.

[3개 프로그램 통합 시험](docs/integration-test-results.md) · [EXE/APK 빌드·Ubuntu 배포 절차](docs/build-and-deploy.md)

## Windows GUI 빠른 시작

기존 `.venv`가 있다면 가상환경 생성 단계는 생략하세요.

```powershell
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python windows-app/run_gui.py
```

1. 최초 설정 마법사에서 Mock 모드를 선택하면 서버/API 키 없이 시작할 수 있습니다.
2. **뉴스 수집** → **선택 뉴스를 글쓰기로** → 출처 검토 확인 → **AI 글 생성**을 실행합니다.
3. **이미지 생성**에서 PNG를 생성·저장합니다. 글은 본문 복사 또는 텍스트 저장을 제공합니다.
4. **예약 스케줄**에서 시간·요일을 저장하고 ON으로 전환합니다. **지금 실행**으로 즉시 시험합니다.
5. 서버를 아래 명령으로 실행한 뒤, **설정**에 동일 토큰을 저장하고 **서버 연결**에서 시험합니다.

설정/뉴스/초안/로그는 `%LOCALAPPDATA%/AI Blog Auto System`에 저장합니다.
키와 토큰은 Windows Credential Manager에 저장하며 SQLite에 저장하지 않습니다.
테스트용 저장 경로는 `BLOG_GUI_DATA_DIR`로 지정할 수 있습니다.
상세 화면 동작 및 제한은 [Windows GUI 안내](docs/windows-gui.md)를 확인하세요.

## HTML / 전체 복사 / Word / ZIP

**AI 글쓰기**에서 글을 선택한 뒤 **콘텐츠 출력**으로 이동하세요.
최근 생성 이미지 또는 로컬 이미지 파일을 추가하고 위로/아래로 순서를 바꿀 수 있습니다.
HTML 미리보기·저장, Windows CF_HTML 서식 포함 전체 복사, 이미지 내장 DOCX,
HTML/TXT/DOCX/이미지/manifest ZIP을 제공합니다.

[출력 사용법](docs/content-exports.md) · [출력 검증 결과](docs/phase3-test-results.md) · [스마트에디터 실제 시험 대기 항목](docs/naver-paste-test.md)

## 설치와 실행

목표 환경: Windows 10/11, Ubuntu 20.04, Python 3.11.
실제 검증 환경과 결과는 [Phase 1 결과](docs/test-results.md), [GUI 결과](docs/phase2-test-results.md)에 기록합니다.
프로젝트 루트에서 PowerShell로 실행하세요.

```powershell
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
$env:BLOG_DEVICE_TOKEN = .venv/Scripts/python -c "import secrets; print(secrets.token_urlsafe(32))"
.venv/Scripts/python -m uvicorn app.main:app --app-dir ubuntu-server --host 127.0.0.1 --port 8000
```

두 번째 터미널에도 동일한 토큰을 설정합니다. 토큰을 Git에 저장하지 마세요.

```powershell
$env:BLOG_DEVICE_TOKEN = '<서버와 동일한 토큰>'
$env:BLOG_SERVER_URL = 'http://127.0.0.1:8000'
.venv/Scripts/python windows-app/send_mock_event.py
# 장애 복구 후 대기 이벤트만 재전송
.venv/Scripts/python windows-app/send_mock_event.py --flush-only
```

Ubuntu 로컬 실행(별도로 준비한 Python 3.11 사용):

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r ubuntu-server/requirements.txt
export BLOG_DEVICE_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
.venv/bin/python -m uvicorn app.main:app --app-dir ubuntu-server --host 127.0.0.1 --port 8000
```

서버는 `ubuntu-server/.env.example`을 `.env`로 복사하여 토큰을 설정해도 됩니다.
송신기는 환경변수로 토큰을 설정합니다. 기본 저장 파일은 실행 디렉터리의
`blog_events.sqlite3`와 `outbox.sqlite3`이며 `BLOG_DB_PATH`, `BLOG_OUTBOX_PATH`로 변경합니다.
`BLOG_DEVICE_ID` 기본값은 `WINDOWS-PC-TEST`입니다.

## API

- `GET /api/v1/health`: DB 연결 검사, 인증 불필요.
- `POST /api/v1/events`: `X-Device-Token` 필수. 새 이벤트 `new=true`, 동일 UUID/내용 재전송 `new=false`, 내용 충돌 409.
- `GET /api/v1/events?limit=20`: 인증된 최신순 조회, 최대 100개.
- `GET /api/v1/events?after=0&limit=100`: 수신 순서대로 복구. 마지막 `sequence`를 다음 `after`로 저장하고 빈 목록까지 반복.
- `POST /api/v1/packages`: 인증된 ZIP 업로드, SHA-256 검증, 48시간 보관.
- `GET /api/v1/packages`: 패키지 메타데이터 조회.
- `GET /api/v1/packages/{UUID}/download`: 인증 다운로드. `kind=html|txt|docx|manifest|image` 지원.
- `POST /api/v1/pairing/codes`: 관리자용 일회용 페어링 코드 발급.
- `POST /api/v1/pairing/claim`: Android 읽기 전용 기기 토큰 발급.
- `GET /api/v1/events/ws?after=0`: 인증 WebSocket 이벤트 복구/실시간 알림.
- `PUT /api/v1/devices/me/push`: 페어링된 기기의 FCM 토큰 등록.
- `POST /api/v1/packages/{UUID}/manual-completion`: 관리자/페어링 기기의 명시적 수동 완료 신고. 실제 네이버 게시 검증 아님.
- `http://127.0.0.1:8000/docs`: 각 보호 API의 `x-device-token` 헤더 입력란에 토큰 입력.

계약: `shared/event-schema.json`. 예제: `shared/event-schema.example.json`.
Mock 성공은 `MOCK_PUBLISH_SUCCESS`이며 실제 게시 성공과 구분됩니다.
송신기는 전송 전 SQLite에 저장하고 UUID가 일치하는 성공 응답 후 삭제합니다.
실패 시 종료 코드 1을 반환하고 재실행하면 복구합니다. 자동 주기 재시도는 후속 단계입니다.
하나의 outbox에 대해 송신기를 동시에 여러 개 실행하지 마세요.

## 테스트 및 상태

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/python tests/smoke_local.py
.venv/Scripts/python tests/smoke_gui.py
.venv/Scripts/python tests/smoke_exports.py
```

임시 DB로 인증, 계약, 중복/충돌, 동시 전송, 재시작, 커서 동기화, 오프라인 복구를 검사합니다.

- 구현: Phase 1 이벤트 API/CLI, PySide6 GUI, 설정 마법사, 자격증명 저장,
  서버 연결, 예약, RSS, OpenAI 글·이미지 연동, Mock 모드, 로그인 상태 기록, 로그,
  HTML/CF_HTML/DOCX/ZIP 출력, 초안별 이미지 순서·설명 저장,
  서버 패키지 업로드/다운로드, 48시간 만료 차단, 5분 정리, 6시간·1시간 전 알림 이벤트,
  Android Compose/Mock 앱, 페어링·읽기 전용 토큰, WebSocket, FCM 선택 연동.
- 검증 필요: Python 3.11, Windows 10/11 각각의 실제 데스크톱, 실제 OpenAI 유료 호출 및 공개 RSS, Ubuntu/PostgreSQL.
- Android 실기기의 Wi-Fi/절전/FCM 수신·Keystore·네이버 붙여넣기는 별도 실제 시험 대상입니다.
- 추가 구현: Windows 실패 신고·자동 패키지 생성·GUI 업로드/재시도, Android 수동 완료 신고, Windows EXE 빌드.
- 미구현/비활성: Windows 송신기의 기기별 인증, 네이버 자동 발행 Adapter, EXE/Android 정식 배포 서명.

[Android 빌드·Mock 체험·페어링·FCM 설정](android-app/README.md)
· [Android/서버 Phase 5 검증 결과](docs/phase5-test-results.md)

[패키지 API·Ubuntu 실행·백업 제외 정책](docs/server-packages.md) · [Phase 4 테스트 결과](docs/phase4-test-results.md)

[구조](docs/architecture.md) · [보안](docs/security.md) · [개발 계획](docs/development-plan.md)
