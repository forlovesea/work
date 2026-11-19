# 아키텍처

- windows-app: 기존 Mock CLI와 SQLite outbox, PySide6 GUI, HTML/DOCX/ZIP 출력. 이후 발행 Adapter.
- ubuntu-server: FastAPI, SQLite 이벤트/패키지 메타데이터, 비공개 ZIP 저장. 이후 PostgreSQL/기기별 인증.
- android-app: Kotlin/Compose, StateFlow, SQLiteOpenHelper, WorkManager, Keystore, OkHttp, 선택적 FCM.
- shared: JSON 이벤트 계약. tests: 임시 DB 통합 테스트.

전송 흐름: UUID/UTC 시각 생성 → outbox 커밋 → 인증 POST → 서버 커밋 →
응답 UUID 확인 → outbox 삭제. 응답 유실 시 동일 UUID로 재시도합니다.
UUID 기본 키로 중복을 방지하며 내용 충돌은 409입니다. 기존 events 테이블 구조를 유지합니다.

커서 조회는 발생 시각 대신 수신 sequence 순서로 지연 이벤트를 복구합니다.
Phase 1은 이벤트를 삭제하지 않으며 SQLite rowid를 사용합니다. PostgreSQL 전환 시
명시적 증가 시퀀스와 마이그레이션이 필요합니다. Phase 5는 WebSocket 힌트와 HTTP 커서 동기화를 함께 사용합니다.

목표 DB: devices, device_tokens, events, posts, publishing_jobs, publishing_history,
content_packages, package_files, package_downloads, notification_history,
statistics_snapshots, audit_logs. 현재 서버에는 events, packages, package_downloads,
pairing_codes, mobile_devices가 생성됩니다.

Phase 4: 파일은 공개 웹 경로 밖에 저장하고 인증 다운로드만 허용합니다.
expires_at = upload_completed_at + 48 hours. 요청 시 만료를 즉시 차단하고
5분 정리 작업은 삭제 실패를 재시도합니다. 감사 로그는 파일 본문과 분리합니다.
실제 구현은 `app/packages.py`이며 FastAPI lifespan으로 정리 작업을 시작/종료합니다.
ZIP 단일 사본에서 개별 파일을 메모리로 내려주므로 디스크의 파생 복사본은 없습니다.
단일 호스트 SQLite 트랜잭션으로 업로드/다운로드/정리를 직렬화합니다.

발행 Adapter는 지원 수단을 검증한 경우만 활성화합니다. 발행 미확인은 자동 재발행하지 않고,
실제 게시 URL 등 확인 근거가 있을 때만 성공으로 기록합니다.

## Windows GUI 모듈

- `run_gui.py`: QApplication과 최초 설정 마법사 진입점.
- `blog_gui/storage.py`: SQLite 설정/뉴스/초안/로그, Windows Credential Manager.
- `blog_gui/services.py`: Phase 1 API 연결, 기존 Outbox 재사용, RSS/Atom,
  OpenAI Responses/Images API 및 Mock 구현.
- `blog_gui/scheduling.py`: APScheduler, Asia/Seoul cron, 누락 작업 판정.
- `blog_gui/window.py`: 9개 화면, QThreadPool 작업, GUI 스레드 결과 반영.

네트워크 호출은 작업 스레드에서 수행합니다. 한 번에 하나의 작업만 실행하고,
진행 중에는 작업 버튼을 비활성화합니다. 설정은 작업 시작 시 복사합니다.
종료 시 진행 중인 요청 완료를 기다리도록 안내하며 각 HTTP 요청에 시간 제한을 둡니다.
GUI의 이벤트 대기열은 CLI와 별도 파일이며 같은 UUID 재전송 규칙을 따릅니다.

## 콘텐츠 출력

초안 JSON의 선택적 `images` 배열에 이미지 ID/로컬 경로/설명/AI 표시 문구를 저장합니다.
이전 초안은 배열 없이 그대로 읽을 수 있습니다. GUI 순서 변경은 해당 초안에만 적용됩니다.

`exports.Publication`은 이미지 bytes를 읽어 스냅샷으로 만들고 동일한 block 순서를
HTML/TXT/DOCX에 사용합니다. ZIP은 상대 이미지 경로와 검증용 manifest를 포함합니다.
출력에는 명시적으로 선택한 공개 콘텐츠 필드만 들어갑니다.
`clipboard`는 일반 Windows 실행에서 Win32 등록 형식 `HTML Format`을 직접 작성하고,
offscreen 테스트에서는 QMimeData로 동일 콘텐츠를 검증합니다.
`preview.HtmlPreview`는 생성한 inline PNG 이외의 리소스를 로드하지 않습니다.

## 통합 수동 발행 흐름

Windows `manual.ManualHandoff`가 사용자 실패 신고/수동 전달 요청을 받아 ZIP을 생성하고
`pending-packages`에 고정된 bytes로 저장합니다. 네트워크 장애 후 재시도는 동일 UUID와 SHA-256을 사용합니다.
업로드 응답을 잃어도 서버는 기존 업로드의 만료 시각을 연장하지 않고 동일 결과를 반환합니다.
GUI의 대기 업로드 재시도 버튼은 대기 패키지와 이벤트 outbox를 함께 전송합니다.
상시 자동 재시도 데몬은 없으며 사용자가 재시도하거나 다음 전달 작업을 실행해야 합니다.

Android는 서버 이벤트를 HTTP 커서로 복구하고 WS/FCM을 알림 신호로 사용합니다.
다운로드 후 사용자가 공식 편집기에서 직접 게시하고 완료를 신고합니다.
서버 `manual.py`는 패키지별 멱등 완료 이벤트를 만들며 실제 네이버 페이지를 요청하지 않습니다.
정확한 권한과 네이버 기능 제한은 [발행 정책](naver-publication-policy.md)을 참조하세요.
