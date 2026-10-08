# Android 앱

Java 17 / Android SDK 35 기반 Android 프로젝트입니다. 장비 목록, 모듈·셀 상세, 이력, 알람 확인, 서버 설정 화면을 구현했습니다.

## 구현 기능

서버·모니터링 클라이언트와의 구성도, 토큰·TLS 인증서, 앱 연결 및 운영 절차는 [통합 개발·운영 상세서](../docs/developer-guide.md)에 정리되어 있습니다.

- 서버 주소(HTTPS 호스트/IP 및 포트), 로그인, 알림 권한 설정
- 현장 및 장비 목록, 모듈별 통신 상태·SOC/SOH, 셀 온도·전압, 방전 횟수, 충전 보호 및 제한 상태 화면
- 최신 상태 화면에서 온라인 모니터링 클라이언트를 통한 충전전류제한 변경 요청과 장비 GET 검증 결과 표시
- 측정 시각과 서버 수신 시각 표시, 오래된 데이터와 통신 두절 표시
- 활성 장비 알람을 발생 시각·시스템/모듈·등급·내용으로 표시하고, Critical/Major/Minor/Warning 등급별 색상 구분
- 알람 발생/복구 이력 조회 및 사용자 확인 처리
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
시험용 APK: [BatteryWatch 0.2.8 장비 알람 반영 APK 다운로드 (2026-10-06)](https://github.com/forlovesea/work/raw/refs/heads/main/BatteryWatch/android-app/releases/BatteryWatch-0.2.8-alarms-20261006.apk). 기존 디버그 APK와 서명이 다르면 업데이트 설치 대신 기존 앱을 제거한 뒤 설치하세요.

서버에서 `python server.py enable-api`로 조회 토큰을 생성한 뒤 `android-connection.local.json`의 서버 주소와 토큰을 앱에 입력합니다. 수집기 업로드 토큰과 다릅니다.
기본 API 포트는 8443입니다. 에뮬레이터 로컬 시험 주소는 `http://10.0.2.2:8443`이며 HTTP는 debug 빌드의 루프백/에뮬레이터 주소만 허용합니다. 실제 휴대폰은 유효한 인증서의 HTTPS 주소를 사용하세요.

## 고객용 오프라인 Release APK

고객사가 보유한 서명 keystore가 없다면 먼저 Windows PowerShell에서 새 keystore를 만듭니다. 기본 저장 경로는 저장소 바깥의 `%USERPROFILE%\BatteryWatchSigning\BatteryWatch-Android-Release.jks`입니다. 다른 경로를 입력해도 저장소 내부 경로는 허용하지 않습니다.

```powershell
.\create-customer-release-keystore.ps1
```

스크립트는 alias와 인증서 common name을 요청하고, 새 비밀번호는 숨김 프롬프트에서 두 번 입력받아 일치 여부를 검사합니다. 비밀번호는 keytool 명령행에 직접 넣지 않고 현재 프로세스의 임시 환경 변수로 전달한 뒤 제거합니다. keystore 및 비밀번호를 별도 안전한 위치에 백업하세요. 기존 파일은 덮어쓰지 않습니다.

생성이 끝나면 서명 APK를 빌드합니다.

```powershell
.\build-offline-release.ps1
```

빌드 스크립트가 keystore 경로와 alias를 다시 요청하고, 비밀번호는 표시되지 않는 보안 프롬프트로 받습니다. 빌드 성공 시 서명된 APK와 Android ZIP이 `..\dist\customer-release\`에 생성되고 SHA-256이 기록됩니다. 향후 앱 업데이트에도 같은 keystore와 alias를 사용해야 합니다. 키를 분실하면 기존 설치 앱을 같은 서명으로 업데이트할 수 없습니다.

## Firebase 빌드

1. Firebase 프로젝트에 `com.batterywatch.monitor`(release), `com.batterywatch.monitor.debug`(debug)를 등록합니다.
2. 프로젝트의 `google-services.json`을 `app/`에 놓습니다. 커밋하지 않습니다.
3. `.\gradlew.bat :app:assemblePushDebug`로 빌드합니다. Linux에서는 `sh gradlew`를 사용합니다. 파일이 없으면 명시적으로 실패합니다.
4. 서버 서비스 계정과 `push` 설정을 적용하고 앱에서 알림 권한을 허용합니다.

서버 알람 규칙과 설정은 [알람·푸시 안내](../docs/alarms-and-push.md)를 참고하세요. 실제 Firebase 수신 시험은 운영 자격증명과 휴대폰이 필요합니다.

## GitHub 배포 0.2.9

[APK 및 릴리스 안내](https://github.com/forlovesea/work/releases/tag/batterywatch-android-v0.2.9)

0.2.9(versionCode 11)는 기존 0.2.8 APK와 같은 앱 ID `com.batterywatch.monitor.offline.debug` 및 디버그 서명을 유지한 배포입니다. 기존 디버그 앱 위에 업데이트 설치할 수 있습니다. 고객용 Release 서명 빌드 및 Google Play 배포본과는 구분됩니다. Firebase 푸시가 없는 조회용 빌드이며 서버 네트워크 연결이 필요합니다.