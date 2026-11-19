# Android Phase 5 검증 결과

검증일: 2026-11-18. 로컬 Windows에서 실행했습니다.
운영 서버 배포, 실제 Firebase 발송, 실기기 설치는 수행하지 않았습니다.

## 결과

| 검사 | 결과 |
|---|---|
| Android Debug APK | assembleDebug 성공 |
| Kotlin/Android 로직 Mock 시험 | Robolectric 14개 통과 |
| Compose 버튼 흐름 시험 | Robolectric 1개 통과 |
| Android 합계 | 15개, 실패/오류 0 |
| Android Lint | 오류 0, 경고 26 |
| 서버·Windows 기존 기능 회귀 | pytest 72개 통과, 종료 코드 0 |
| 실제 로컬 HTTP/WebSocket 통신 | 페어링·읽기 권한·실시간 이벤트·ZIP·만료 차단 통과 |
| APK 개발용 서명 | apksigner v2 검증 통과 |

환경: JDK 17.0.20.1, Gradle 8.11.1, AGP 8.9.2, Kotlin 2.1.20,
Android SDK/Build Tools 35/35.0.0. Robolectric JVM 시험 런타임은 API 28입니다.
앱의 minSdk는 26, target/compileSdk는 35입니다.
서버 시험은 기존 Python 3.10.11 가상환경을 사용했습니다.

실행 명령:

```powershell
# android-app 폴더
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug --no-daemon --console=plain

# 프로젝트 루트
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests/smoke_local.py
```

Android 결과: `BUILD SUCCESSFUL`. pytest: `72 passed, 1 warning in 27.96s`.
실제 통신 시험:

```text
PASS: real HTTP server + CLI + persisted event + empty retry
PASS: real HTTP ZIP upload/download + auth + duplicate + immediate expiry denial
PASS: real HTTP pairing + read-only token + live WebSocket event
```

## 시험 범위

- HTTPS와 debug 로컬 주소 정책, URL의 사용자정보·경로·쿼리 거부.
- 일회용 코드의 재사용/10분 만료, 동시 교환 1개만 성공.
- 90일 Android 토큰 만료, 관리자 폐기, 토큰 해시 저장.
- Android 토큰의 읽기 허용/작성·업로드·관리자 API 차단.
- WebSocket 인증, 커서 재생, 신규 이벤트, 폐기 후 연결 종료.
- FCM 등록, 설정 없는 모드, 가짜 발송기 실패 후 재시도, 토큰 회전, 기기 폐기.
- 앱 SQLite UUID 중복 제거/커서 후퇴 방지/재시작/서버별 분리.
- 오프라인 실패 중 이력·커서 보존과 Mock 복구.
- FCM 힌트의 중복 알림 제거와 HTTP로 가져오기 전 커서 이동 방지.
- Mock ZIP/Word 다운로드, SHA-256 오류와 410 처리.
- 이미지 3장의 manifest 순서와 미리보기 data URI 바이트 일치.
- ZIP 경로 조작·변조·만료 거부, HTML 스크립트/핸들러/외부 이미지 제거.
- WebView의 inline PNG 허용과 HTTP/file/content/HTML data 리소스 차단.
- 48시간 만료 경계와 남은 시간 표시, Mock 성공과 실제 성공 집계 분리.
- 큰 HTML 이미지의 클립보드 한도 처리: 전체 본문 보존, 이미지 제외 안내, 본문 잘라내기 없음.
- Compose 화면에서 최초 Mock 시작 → 대시보드 → 이력 → 콘텐츠 → Word 다운로드 →
  HTML 미리보기 → 전체 복사 → 닫기를 실제 버튼으로 실행했습니다.
  ClipboardManager의 HTML/일반 텍스트를 원본과 비교했습니다.

Robolectric의 WebView는 실제 Chromium 픽셀 렌더링과 동일한 시험이 아닙니다.
URI 허용 정책과 생성 HTML/이미지 bytes는 자동 검증했으며 실제 표시 품질은 단말에서 확인해야 합니다.
Android Keystore의 하드웨어 보호, OS Wi-Fi 이벤트/절전 스케줄링은 실제 기기 검증이 남아 있습니다.

## 경고와 미실시 항목

Lint 26개 경고는 최신 의존성 버전 안내, SharedPreferences의 apply 권고,
KTX 편의 함수 사용 권고입니다. Lint 검사를 비활성화하거나 baseline으로 오류를 숨기지 않았습니다.
SDK XML 버전 차이 안내와 debug 네이티브 라이브러리 strip 안내가 있었으나 빌드는 성공했습니다.
pytest 경고는 기존 Starlette TestClient의 httpx 폐기 예정 안내입니다.

실제 기기/Firebase 설정 후 별도 확인:

1. Wi-Fi 끊김·복구, 화면 복귀, 프로세스 종료 후 누락 이벤트 복구.
2. Android 13+ 알림 허용/거부, FCM 토큰 회전, 백그라운드·절전·강제 종료 상태.
3. Keystore 재시작/복원 실패 처리, cloud backup과 기기 간 전송 제외 정책.
4. 큰 파일·저장 공간 부족, SAF 저장과 Office/파일 앱 공유.
5. HTML 이미지 실제 표시와 [네이버 붙여넣기 별도 시험](naver-paste-test.md).
6. Firebase 서비스 계정과 실제 data 메시지 발송. 이번 시험은 외부 푸시를 보내지 않았습니다.

## 산출물

- APK: `android-app/app/build/outputs/apk/debug/app-debug.apk`
- 최종 APK 크기: 12,843,531 bytes. 재연결 작업 취소 수정 포함, 최종 빌드 성공 및 v2 서명 검증 완료.
- SHA-256: `A7ADEFCD95984BE117F34F0F01DE44B1CFFB62508C23AAA74014FB7B42F9828F`
- Android 시험 보고서: `android-app/app/build/reports/tests/testDebugUnitTest/index.html`
- Lint 보고서: `android-app/app/build/reports/lint-results-debug.html`
- 빌드·설정·페어링·FCM 안내: [Android README](../android-app/README.md)

개발용 서명 APK이며 Play Store 배포 서명과 등록은 포함하지 않습니다.
