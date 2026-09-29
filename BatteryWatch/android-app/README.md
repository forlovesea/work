# Android 앱

Java 17 / Android SDK 35 기반 Android 프로젝트입니다. 장비 목록, 모듈·셀 상세, 이력, 알람 확인, 서버 설정 화면을 구현했습니다.

## 구현 기능

- 서버 주소(HTTPS 호스트/IP 및 포트), 로그인, 알림 권한 설정
- 현장 및 장비 목록, 모듈 SOC/SOH, 셀 온도·전압 화면
- 측정 시각과 서버 수신 시각 표시, 오래된 데이터와 통신 두절 표시
- 활성 알람/복구 이력 조회 및 사용자 확인 처리
- FCM 토큰 등록·갱신·로그아웃 시 해제
- 알림 탭 시 관련 장비와 알람 상세 화면 열기

Java 기반 네이티브 앱입니다. 화면이 열려 있을 때만 설정 주기(5~300초)로 조회합니다. 푸시 빌드에서는 화면이 닫혀 있을 때 FCM으로 알림을 수신합니다. 조회 토큰은 Android Keystore로 암호화해 저장합니다.

서버/토큰 변경 및 로그아웃 시 이전 서버의 알림 등록을 해제합니다. 이전 서버에 연결할 수 없어 해제에 실패하면 설정 변경을 중단하고 오류를 표시합니다. FCM 등록 실패는 앱 재실행이나 설정 저장 시 재시도합니다.

FCM 설정과 실제 기기에서의 화면 꺼짐/재부팅/강제 종료/네트워크 단절 시험은 구현 후 별도로 필요합니다.

## 빌드와 실행

JDK 17, Gradle 8.11.1, Android SDK `platforms;android-35` 및 `build-tools;35.0.0`을 준비합니다. Android Studio로 이 디렉터리를 열거나 다음을 실행합니다.

```powershell
.\gradlew.bat :app:assembleOfflineDebug :app:testOfflineDebugUnitTest
```

출력: `app/build/outputs/apk/offline/debug/app-offline-debug.apk`
`offline`은 Firebase 없는 **조회 전용 빌드** 이름이며 서버 네트워크 연결은 필요합니다. 백그라운드 푸시를 제공하지 않습니다.

서버에서 `python server.py enable-api`로 조회 토큰을 생성한 뒤 `android-connection.local.json`의 서버 주소와 토큰을 앱에 입력합니다. 수집기 업로드 토큰과 다릅니다.
기본 API 포트는 8443입니다. 에뮬레이터 로컬 시험 주소는 `http://10.0.2.2:8443`이며 HTTP는 debug 빌드의 루프백/에뮬레이터 주소만 허용합니다. 실제 휴대폰은 유효한 인증서의 HTTPS 주소를 사용하세요.

## Firebase 빌드

1. Firebase 프로젝트에 `com.batterywatch.monitor`(release), `com.batterywatch.monitor.debug`(debug)를 등록합니다.
2. 프로젝트의 `google-services.json`을 `app/`에 놓습니다. 커밋하지 않습니다.
3. `.\gradlew.bat :app:assemblePushDebug`로 빌드합니다. Linux에서는 `sh gradlew`를 사용합니다. 파일이 없으면 명시적으로 실패합니다.
4. 서버 서비스 계정과 `push` 설정을 적용하고 앱에서 알림 권한을 허용합니다.

서버 알람 규칙과 설정은 [알람·푸시 안내](../docs/alarms-and-push.md)를 참고하세요. 실제 Firebase 수신 시험은 운영 자격증명과 휴대폰이 필요합니다.
