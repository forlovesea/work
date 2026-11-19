# 개발 계획

1. Phase 1: 이벤트 API/Mock CLI, 계약/문서/통합 테스트. 로컬 SQLite.
2. Phase 2: PySide6 최초 설정, AI 글/이미지, 출처/중복 검사, OS 비밀정보 보관.
3. Phase 3: HTML/CF_HTML/DOCX, 이미지 내장, manifest/해시/ZIP. 실제 붙여넣기 검증.
4. Phase 4: PostgreSQL/Alembic, 기기 인증, 파일 업로드/다운로드, 48시간 만료 및 알림.
5. Phase 5: Android Compose/Room, Wi-Fi 재연결, 커서 동기화, WebSocket/FCM, 다운로드/복사.
6. Phase 6: 네이버 공식 인증 및 지원 가능한 발행 Adapter 검증, 중복 발행 방지.
7. Phase 7: 요구서 25개 시나리오, 배포/복구 검증, EXE/APK 빌드.

각 단계에서 소스, 테스트, 실행 방법, 오류 수정, README와 상태표를 함께 갱신합니다.
수행하지 않은 검증을 완료로 표시하지 않습니다. Phase 1 테스트는 Android나 만료 테스트를 대신하지 않습니다.
Phase 2 GUI 구현 및 Mock/테스트 응답 기반 자동 검증을 완료했습니다.
실제 OpenAI 호출, 공개 RSS, Windows 10/11 및 Python 3.11 환경 검증은 남아 있습니다.
Phase 3 HTML/CF_HTML/DOCX/ZIP 출력과 이미지 순서 자동 검증을 구현했습니다.
네이버 스마트에디터 붙여넣기 호환성은 `naver-paste-test.md`의 별도 실제 시험 대상입니다.
Phase 4 서버 콘텐츠 업로드/다운로드/48시간 만료·알림·삭제를 기존 SQLite 기반으로 구현했습니다.
PostgreSQL/Alembic, Windows 기기별 인증과 실제 Ubuntu 검증은 남아 있습니다. GUI 업로드는 통합 단계에서 연결했습니다.
Phase 5는 Kotlin/Compose Android 앱과 단말 없는 Mock/Robolectric 시험을 추가했습니다.
Android 일회용 페어링, 90일 읽기 토큰/폐기, Wi-Fi 복구, WebSocket, 선택적 FCM을 구현했습니다.
실제 FCM/절전/단말별 HTML 붙여넣기와 배포 서명은 별도 검증 대상입니다.
실제 외부 서버 변경은 승인 및 백업 후 수행합니다.

통합 단계: Windows EXE 및 Android APK 빌드, 실제 로컬 HTTP/WS 연결,
실패 신고 → 자동 패키지 → 업로드/알림 → 다운로드 → 수동 완료 → 만료/삭제 시험을 추가했습니다.
네이버 글쓰기 API/앱 글쓰기 Scheme 종료를 공식 공지로 확인하여 자동 발행은 비활성 상태로 유지합니다.
자세한 완료/미실시 범위는 [통합 시험 결과](integration-test-results.md)에 구분합니다.

커밋 준비 시 .env/DB/outbox/가상환경을 제외하고 diff와 테스트 결과를 확인합니다.
현재 상위 저장소 소유권 경고는 전역 safe.directory를 임의 변경하지 않고 별도 점검합니다.
자동 커밋/푸시는 수행하지 않습니다.
