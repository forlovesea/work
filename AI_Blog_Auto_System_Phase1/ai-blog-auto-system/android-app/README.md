# AI Blog Monitor — Android Phase 5

Kotlin + Jetpack Compose 앱입니다. API 26(Android 8) 이상, compile/target SDK 35.
기본 Mock 모드는 단말, 서버, Firebase 계정, API 키 없이 작동합니다.
대시보드/이벤트/콘텐츠/설정 화면과 최초 연결 마법사를 제공합니다.

## 빌드와 단말 없는 시험

필요 환경: JDK 17, Android SDK Platform 35 + Build Tools 35.0.0, 첫 의존성 다운로드용 인터넷.
Gradle Wrapper 8.11.1, AGP 8.9.2, Kotlin/Compose 플러그인 2.1.20을 고정했습니다.
Android Studio로 이 폴더를 열거나 JAVA_HOME과 ANDROID_HOME을 설정합니다.
SDK 위치는 미추적 `local.properties`에 `sdk.dir=...`로 지정해도 됩니다.

```powershell
cd android-app
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug --no-daemon
```

Linux/macOS에서는 `sh gradlew`로 같은 작업을 실행합니다.

- APK: `app/build/outputs/apk/debug/app-debug.apk`
- JVM/Robolectric: `app/build/reports/tests/testDebugUnitTest/index.html`
- Lint: `app/build/reports/lint-results-debug.html`
- Mock 파일: `app/src/main/assets/mock-package.zip` (Phase 3 출력기의 이미지 내장 DOCX 포함)
- Fixture 재생성: 루트에서 `.venv/Scripts/python tests/create_android_mock.py`

Robolectric은 JVM에서 Android와 Compose 버튼을 시험하므로 단말/에뮬레이터가 필요 없습니다.
첫 실행에는 시험용 Android 런타임을 다운로드합니다. APK는 개발용 서명입니다.

## Mock 체험

처음 실행 → Mock 모드 시작 → 대시보드 → 이벤트/콘텐츠.
Mock 알림 발생 버튼은 새 수동 발행 요청을 추가하고 로컬 알림을 생성합니다.
Android 13 이상에서는 설정 화면에서 알림 권한을 허용하세요.
Word/ZIP/HTML 다운로드, 이미지 포함 HTML 미리보기, HTML+일반 텍스트 전체 복사를 지원합니다.
다운로드 후 저장 위치 선택(SAF) 또는 파일 공유를 사용할 수 있습니다.
Mock 성공은 실제 발행 성공 집계와 구분합니다. Mock 패키지는 최초 시작 후 48시간에 만료됩니다.
반복 체험 시 앱 데이터를 초기화할 수 있습니다.

## 서버 페어링

이 저장소의 Phase 5 서버 변경이 필요합니다. 기존 Phase 4에는 페어링/WebSocket이 없습니다.
운영 서버에 자동 접속하거나 배포하지 않습니다.

1. BLOG_DEVICE_TOKEN은 관리자/Windows 송신용입니다. Android에 입력하지 않습니다.
2. 관리자 PC에서 `POST /api/v1/pairing/codes`를 호출합니다.
3. 응답의 32자리 일회용 코드를 Android 설정에 입력합니다. 유효 기간은 10분입니다.
4. 앱은 `/api/v1/pairing/claim`으로 90일 유효 제한 권한 토큰을 받습니다.
5. Android Keystore AES-GCM으로 저장합니다. 실패 시 평문 저장으로 대체하지 않습니다.

```powershell
$headers = @{ 'X-Device-Token' = $env:BLOG_DEVICE_TOKEN }
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/pairing/codes' -Method Post -Headers $headers
```

서버에는 코드/기기 토큰의 SHA-256만 저장합니다. 관리자 인증으로 `GET /api/v1/devices`에서
등록 목록을 보고 `DELETE /api/v1/devices/{device_id}`로 폐기합니다.
Android 토큰은 이벤트/패키지 읽기, 자신의 FCM 등록, 수동 발행 완료 신고를 허용합니다.
임의 이벤트 작성이나 패키지 업로드는 허용하지 않습니다.
같은 서버에 페어링된 기기는 운영 이력/콘텐츠를 공유합니다. 사용자별 테넌트 격리는 없습니다.

실제 연결은 정상 인증서의 HTTPS가 필요하며 TLS 우회 옵션은 없습니다.
Debug만 http://10.0.2.2:8000(에뮬레이터→PC), localhost, 127.0.0.1을 허용합니다.
Release는 HTTPS 전용입니다. 사용자정보/경로/쿼리가 붙은 서버 주소를 거부합니다.
에뮬레이터 네트워크 분류가 Wi-Fi가 아니면 시험 시 Wi-Fi 전용 설정을 해제하세요.

## 재연결과 이력

- 화면 진입/복귀 시 저장된 sequence 다음부터 HTTP 전체 페이지를 복구합니다.
- 전경에서는 인증 헤더를 넣은 `/api/v1/events/ws?after=<cursor>`에 연결합니다.
- 소켓 이벤트는 직렬화된 HTTP 동기화를 깨우는 신호입니다. FCM/소켓 sequence만 보고 커서를
  옮기지 않아 콜백 순서와 무관하게 누락 구간을 복구합니다.
- UUID 중복 제거와 커서는 SQLite 트랜잭션으로 저장하며 서버·기기별 이력을 분리합니다.
- Wi-Fi 복구를 ConnectivityManager로 감지하고 1~30초 간격으로 재시도합니다.
- 백그라운드에서는 소켓을 닫고 FCM/네트워크 복구 시 WorkManager와 15분 주기 보완 작업을 사용합니다.
- 오프라인에는 저장된 마지막 상태를 표시합니다. 이력과 오늘 카운터는 최근 1,000개 이벤트 기준입니다.
  공식 조회수 수집이나 게시 상태를 임의로 성공 처리하는 기능은 없습니다.

## 실제 FCM 설정(선택)

설정 없이도 빌드/Mock 시험이 가능합니다. 실제 푸시 설정:

1. Firebase에 applicationId `com.aiblog.monitor`를 등록합니다.
2. `google-services.json`을 `app/`에 넣습니다. 파일이 있을 때만 Google Services 플러그인을 적용합니다.
3. 서버에 `pip install -r ubuntu-server/requirements-fcm.txt`를 실행합니다.
4. 서비스 계정 JSON은 서버에만 권한을 제한하여 보관하고 BLOG_FCM_CREDENTIALS로 경로를 지정합니다.
5. 앱 페어링과 알림 권한을 설정하면 `/api/v1/devices/me/push`에 FCM 토큰을 등록합니다.

서버는 5초 주기로 FCM data 메시지(event_id, event_type, sequence)를 발송합니다.
본문/이미지/인증 토큰은 payload에 넣지 않습니다. 실패 시 커서를 유지하고 재시도합니다.
첫 등록 이전 이력은 HTTP로만 복구합니다. 중복 도착은 클라이언트 UUID로 제거합니다.
절전/강제 종료/Google Play Services 상태에 따라 수신이 지연될 수 있으며 영속 이벤트 API가 원본입니다.
서비스 계정 파일을 앱/저장소에 넣지 마세요. 실제 Firebase 발송은 자격증명 없이 검증할 수 없습니다.

## 콘텐츠 안전성과 만료

- 헤더 SHA-256 검증, ZIP 목록 해시 대조, 최대 100 MiB 스트리밍 다운로드.
- 비공개 임시 파일을 검증 후 이동하며 부분 파일은 삭제합니다. 명시적 SAF/공유만 외부에 노출합니다.
- 미리보기는 ZIP 16 MiB, 확장 합계 24 MiB, HTML/TXT 각각 2 MiB 제한입니다. 큰 콘텐츠는 다운로드를 사용합니다.
- ZIP은 추출하지 않고 이름/중복/크기/manifest 해시를 검사합니다. 이미지 data URI를 넣고 Jsoup 허용 목록으로 HTML을 정리합니다.
- WebView의 JavaScript, 파일/콘텐츠 접근, 외부 네트워크, DOM 저장소, 탐색을 차단합니다.
- 남은 시간은 매초 갱신하고 만료 정각에 다운로드/복사를 막습니다. 서버 410이 최종 검사입니다.
  휴대폰 시계가 틀리면 표시가 다를 수 있습니다.
- 명시적으로 내려받은 복사본은 기기에 남습니다. 서버 만료가 사용자 파일을 삭제하지 않습니다.
- 앱 비공개 파일/DB/설정은 cloud backup과 기기 간 전송에서 제외하도록 XML 정책을 지정했습니다.
- Android HTML 클립보드의 이미지 붙여넣기는 대상 앱별 실제 시험이 필요합니다.
  Binder 용량 한도를 넘는 큰 이미지는 알림과 함께 제외하고 전체 본문을 보존합니다.
  서식도 크면 일반 텍스트로 복사하며, 본문 자체가 256 KiB를 넘으면 자르지 않고 Word/ZIP 사용을 안내합니다.
  Windows CF_HTML을 재현하는 기능은 아니며 네이버 스마트에디터 호환성은 미검증입니다.

## 코드와 공식 참고 문서

MainActivity: 화면/SAF/클립보드/WebView. MonitorRepository: 상태·동기화·재연결.
Api: OkHttp/Mock. LocalStore: SQLite/Keystore. Background: FCM/네트워크/WorkManager.
Preview: ZIP/HTML 검증. 서버는 `ubuntu-server/app/mobile.py`입니다.

- [AGP 8.9 호환 JDK/Gradle](https://developer.android.com/build/releases/agp-8-9-0-release-notes)
- [네트워크 상태 감지](https://developer.android.com/develop/connectivity/network-ops/reading-network-state)
- [WebView 리소스 차단(data URI 포함)](https://developer.android.com/reference/android/webkit/WebViewClient)
- [Firebase Android 설정](https://firebase.google.com/docs/android/setup)
- [FCM Android와 알림 권한](https://firebase.google.com/docs/cloud-messaging/android/get-started)
# 통합 시험 추가 사항

콘텐츠 화면의 **수동 발행 완료 기록**은 사용자가 공식 편집기에서 직접 게시한 뒤 URL을 입력하는 기능입니다.
명시적인 확인 후 `MANUAL_PUBLISH_COMPLETED` 이벤트를 생성하며 실제 네이버 게시 여부를 검증하지 않습니다.
Mock에서는 서버에 쓰지 않고 Mock 이력에만 기록합니다. 자동 발행, 비공식 API, 종료된 앱 URL Scheme은 사용하지 않습니다.
페어링 토큰은 이벤트/패키지 읽기와 본인 푸시 등록, 이 제한된 완료 신고 API만 사용할 수 있습니다.

[통합 시험 결과](../docs/integration-test-results.md) · [빌드와 배포 절차](../docs/build-and-deploy.md)
