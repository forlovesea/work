# Windows GUI 검증 결과

검증일: 2026-11-17 (Asia/Seoul).
환경: Windows 실행 환경, Python 3.10.11, PySide6 6.12.0, Qt offscreen 렌더링.
목표 환경인 Windows 10/11 각각과 Python 3.11을 모두 검증한 것은 아닙니다.

## 최종 자동 테스트

```text
.venv/Scripts/python -m pytest -q
39 passed, 1 warning in 4.47s
```

기존 Phase 1 테스트 17개와 Phase 2 테스트 22개가 통과했습니다.

- 최초 설정 마법사의 Next/Finish, 설정 영속 저장, 비밀정보 SQLite 미포함
- 서버 연결/인증, Mock 전송, 대기열 비우기, 인증 설정 누락 시 오류 표시
- 뉴스 수집/선택/출처 열기/글쓰기로 전달/출처 확인 필수 검사
- 글 생성/과거 초안 조회/클립보드/UTF-8 내보내기
- Mock PNG 생성/해상도/미리보기/파일 저장
- 실제 OpenAI 요청 형식 및 텍스트/이미지 응답 처리 (HTTP 테스트 응답 사용)
- 불완전 응답, 잘못된 JSON/필드 거부, 토큰이 포함된 HTTP 오류의 로그 노출 방지
- 실제 RSS 형식 파싱 (테스트 응답), 중복 URL, 잘못된 링크, 2 MiB 제한
- 동일 콘텐츠 재수집 및 최근 100건을 넘어선 초안의 중복 방지, DB 재개방
- Asia/Seoul/요일 cron, 예약 설정 저장/ON/OFF/즉시 실행, 실제 scheduler callback
- 누락 작업 판정과 경고 전달, 백그라운드 작업 중 UI 응답 및 종료 방지
- 사용자 신고 로그인 상태, 초기화, 공식 URL 열기 요청 (브라우저 실행은 테스트 대역 사용)
- 로그 수준 필터/내보내기/삭제와 대시보드 갱신

기존 Starlette TestClient의 httpx deprecation 경고 1건은 남아 있습니다.
`pip check`는 `No broken requirements found`를 반환했습니다.

## 실제 로컬 프로세스 통합 시험

```text
.venv/Scripts/python tests/smoke_local.py
Acknowledged events: 1
Acknowledged events: 0
PASS: real HTTP server + CLI + persisted event + empty retry

.venv/Scripts/python tests/smoke_gui.py
PASS: Qt GUI buttons + real HTTP auth/events + Mock news/article/PNG + encrypted credentials
PASS: 3 event types persisted on Phase 1 server; no external service requests
```

GUI 통합 시험은 실제 loopback Uvicorn 서버를 별도 프로세스로 실행했습니다.
Qt 버튼을 통해 서버 인증, Mock 뉴스 수집, 글/PNG 생성 및 이벤트 전송을 수행했습니다.
서버에 MOCK_PUBLISH_SUCCESS, CONTENT_GENERATED, IMAGE_GENERATED가 저장된 것을 확인했습니다.
테스트 전용 Windows Credential Manager 항목을 실제 저장·조회·삭제했습니다.
서버 프로세스와 임시 데이터는 시험 종료 시 정리했습니다.

제한된 샌드박스 세션에서 Credential Manager 저장은 WinError 1312로 실패했습니다.
승인된 일반 Windows 실행 환경에서 재시험하여 통과했습니다.
일반 사용자 로그인 세션이 없는 환경에서 비밀정보를 평문 저장으로 대체하지 않습니다.

## 화면 확인

대시보드, 글쓰기, 이미지 화면을 Qt로 렌더링해 캡처하고 직접 확인했습니다.
최초 offscreen 렌더링에서 한글이 사각형으로 표시되는 문제를 발견하여
Windows 맑은 고딕을 명시적으로 로드하도록 수정했습니다. 수정 후 한글 표시와
본문/버튼/이미지 배치를 확인했습니다.

## 아직 검증하지 않은 항목

- 실제 OpenAI 계정의 유료 글·이미지 생성, 모델 권한 및 실제 서비스 응답
- 공개 RSS 서버에 대한 실제 네트워크 수집 (RSS 파싱/HTTP 오류는 테스트 응답 검증)
- 기본 브라우저를 통한 실제 네이버 로그인 및 로그인 세션 자동 확인
- Windows 10/11 각각의 물리적 데스크톱, DPI 설정, 절전/재부팅, Python 3.11
- 패키징된 EXE, HTML/CF_HTML/DOCX, 자동 발행, Android/FCM

운영 서버 배포·운영 DB·방화벽 변경은 수행하지 않았습니다.
Phase 1 서버/CLI 소스는 수정하지 않았습니다.

현재 상위 Git 저장소에서는 이 프로젝트 폴더가 untracked로 표시됩니다.
커밋/푸시는 수행하지 않았으며 전역 Git 설정도 변경하지 않았습니다.
