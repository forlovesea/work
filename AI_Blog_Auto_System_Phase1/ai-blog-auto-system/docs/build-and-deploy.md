# Windows·Android 빌드 및 Ubuntu 배포 절차

이 문서는 검토용 절차입니다. 운영 서버에 명령을 실행하거나 배포하지 않았습니다.
운영 반영은 대상 호스트·도메인·릴리스·백업 위치를 확정하고 사용자 승인을 받은 뒤 수행합니다.

## Windows 10/11 x64

프로젝트 루트에서 실행합니다. 빌드에 사용한 환경은 Windows 10 build 19045,
Python 3.10.11, PyInstaller 6.16.0입니다. Windows 11의 새 사용자 계정 시험은 별도로 필요합니다.

```powershell
py -3.10 -m venv .venv
.venv/Scripts/python -m pip install -r windows-app/requirements-build.txt
.venv/Scripts/python -m PyInstaller --noconfirm windows-app/AI-Blog-Auto.spec
$env:QT_QPA_PLATFORM='offscreen'
$process = Start-Process -FilePath '.\dist\AI-Blog-Auto\AI-Blog-Auto.exe' -ArgumentList '--self-test','build/exe-smoke' -WindowStyle Hidden -PassThru -Wait
Get-Content build/exe-smoke/result.json
Remove-Item Env:QT_QPA_PLATFORM
```

결과는 `dist/AI-Blog-Auto/AI-Blog-Auto.exe`와 `_internal`입니다.
**EXE 단독으로 복사하지 말고 폴더 전체를 전달**합니다. 배포 ZIP은 폴더 전체를 압축합니다.
자체 시험은 외부 API·실계정 없이 Qt 화면 초기화, Mock 글·이미지, DOCX/ZIP, 로그인 기록을 검사합니다.
실행 때 가상환경이나 Python 설치는 필요 없습니다. 처음 실행하면 설정 마법사가 열립니다.
실제 GUI 실행에는 `QT_QPA_PLATFORM=offscreen`을 설정하지 않습니다.
데이터는 `%LOCALAPPDATA%/AI Blog Auto System`, 키는 Windows Credential Manager에 저장됩니다.
이번 EXE에는 Authenticode 배포 서명이 없습니다. 공식 배포 전 소유 인증서로 서명하고 새 PC에서 시험합니다.
검증 환경의 패키지 버전은 `docs/integration-python-environment.txt`에 기록합니다.

## Android APK

JDK 17, Android SDK platform 35/build-tools 35.0.0을 준비하고 환경변수를 자신의 경로로 설정합니다.
`android-app/local.properties`의 `sdk.dir`도 사용할 수 있습니다. 개발자 개인 경로는 커밋하지 않습니다.

```powershell
$env:JAVA_HOME='C:\toolchains\jdk-17'
$env:ANDROID_HOME='C:\Android\Sdk'
cd android-app
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug --no-daemon --console=plain
```

결과: `android-app/app/build/outputs/apk/debug/app-debug.apk`.
Debug 키로 서명되어 있으며 실제 배포 서명·Play 등록은 별도입니다.
실기기 연결 시 `adb install -r app/build/outputs/apk/debug/app-debug.apk`로 설치할 수 있습니다.
기본 Mock 모드는 Firebase/API 키 없이 동작합니다. 일반 단위 시험에서는 LiveIntegrationTest가 의도적으로 skip됩니다.

실제 FCM을 사용할 때만 Firebase 콘솔에서 `com.aiblog.monitor` 앱을 등록하고
`app/google-services.json`을 로컬에 넣은 뒤 다시 빌드합니다. 서비스 계정 JSON은 서버에만 둡니다.
서버 `requirements-fcm.txt`와 `BLOG_FCM_CREDENTIALS` 설정 후 페어링·알림 권한을 확인합니다.
Debug 빌드도 평문 HTTP는 127.0.0.1/localhost/10.0.2.2만 허용합니다. 실기기 원격 서버에는 유효한 HTTPS가 필요합니다.
상세 절차: [Android README](../android-app/README.md).

## 세 프로그램 로컬 통합 시험 재현

위 JDK/SDK 환경변수를 설정한 상태에서 프로젝트 루트에서 실행합니다.

```powershell
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python tests/integration_live.py
```

통합 스크립트는 임시 DB·난수 토큰으로 루프백 FastAPI 서버를 실행합니다.
Windows 서비스 코드로 패키지를 만들고, 실제 연결 거부·재시작·복구를 검사한 뒤
Gradle이 실제 Android HttpApi/WebSocket/Preview/알림 코드를 실행합니다.
FCM 경계는 파일에 캡처하는 가짜 발송기로 대체합니다. Google FCM 전송은 없습니다.
마지막에 가상 시계로 6시간·1시간·48시간 경계를 검사하고 임시 서버·파일을 정리합니다.
결과: `build/integration/result.json`, Android 테스트·Lint HTML 보고서.

## Ubuntu 사전 준비와 승인 후 배포

최초 소스 다운로드와 시험 서버 실행은 [Ubuntu 설치 가이드 2~3절](ubuntu-install-use.md#2-github에서-소스-내려받기)을 먼저 진행합니다.
실제 저장소는 `https://github.com/forlovesea/work.git`이고 프로젝트 루트는
`work/AI_Blog_Auto_System_Phase1/ai-blog-auto-system`입니다. 아래 릴리스 배치는 이 프로젝트 루트를 기준으로 합니다.

대상은 별도의 Ubuntu 시험 서버부터 준비합니다. Python 3.10 이상이 필요하며,
이 세션에서는 Ubuntu 커널·systemd·Nginx·POSIX 권한을 실행 검증하지 못했습니다.
Ubuntu 기본 Python이 3.10 미만이면 먼저 호환 런타임을 준비해야 합니다.
아래 명령은 대상 서버를 변경하므로 **승인 전 실행하지 않습니다**.

1. 비특권 서비스 계정 `ai-blog`를 만들고 `/opt/ai-blog/releases/<릴리스>`에 검토한 소스를 배치합니다.
   기존 운영 소스에 덮어쓰지 않습니다. 릴리스에 `.env`, 키, DB, 콘텐츠 ZIP, Windows/Android 빌드 산출물을 포함하지 않습니다.
2. 릴리스 디렉터리에서 `python3 -m venv .venv` 및 `.venv/bin/python -m pip install -r ubuntu-server/requirements.txt`를 실행합니다.
   FCM 사용 시에만 `requirements-fcm.txt`를 설치합니다. 설치 후 `pip freeze`를 릴리스와 함께 보관합니다.
3. `sudo install -d -o ai-blog -g ai-blog -m 0700 /var/lib/ai-blog/metadata /var/lib/ai-blog/packages`로
   메타데이터와 48시간 콘텐츠를 분리합니다. `/etc/ai-blog`는 root 전용으로 만들고 `server.env`를 root:root 0600으로 저장합니다.
   서비스 계정은 소스/가상환경을 읽고 실행할 수 있어야 하며 쓰기는 `/var/lib/ai-blog`로 제한합니다.
4. `server.env`에 다음 값을 설정합니다. 토큰은 난수 32바이트 이상으로 별도 생성·전달하며 로그/소스에 넣지 않습니다.

```dotenv
BLOG_DEVICE_TOKEN=<충분히 긴 난수 관리자 토큰>
BLOG_DB_PATH=/var/lib/ai-blog/metadata/events.sqlite3
BLOG_PACKAGE_DIR=/var/lib/ai-blog/packages
BLOG_PACKAGE_MAX_BYTES=104857600
# FCM을 사용하는 경우에만, 서비스 계정이 읽을 수 있는 별도 비밀 파일:
# BLOG_FCM_CREDENTIALS=/etc/ai-blog/firebase-service-account.json
```

5. `/opt/ai-blog/current`가 승인된 릴리스를 가리키도록 설정하고
   [ai-blog.service](../ubuntu-server/deploy/ai-blog.service)를 `/etc/systemd/system/ai-blog.service`로 설치합니다.
   `sudo systemd-analyze verify /etc/systemd/system/ai-blog.service` 후
   `sudo systemctl daemon-reload` 및 `sudo systemctl enable --now ai-blog`를 실행합니다.
6. `curl --fail http://127.0.0.1:8000/api/v1/health` 및 `systemctl status ai-blog`로 확인합니다.
   NTP 동기화, 재부팅 후 서비스 시작, 디스크 공간·삭제 오류 로그를 점검합니다.
7. [Nginx 예시](../ubuntu-server/deploy/nginx.conf.example)의 도메인과 TLS 인증서 경로를 실제 값으로 바꿉니다.
   처음 설치하는 서버는 [HTTPS 설정 절차](https-setup.md)에 따라 bootstrap → 인증서 발급 → 최종 TLS 설정 순서로 적용합니다.
   `sudo nginx -t` 통과 후에만 reload합니다. 앱 API는 HTTPS 443에서만 제공하고 8000은 루프백에 유지합니다. HTTP 80은 ACME 인증서 발급·갱신과 HTTPS 이동용입니다.
   패키지 경로를 static/alias로 공개하지 않습니다. 요청·응답 캐시/디스크 버퍼도 비활성화합니다.
8. 시험 데이터로 인증 거부, 페어링, Windows 업로드, Android WS/다운로드/수동 완료, 서비스 재시작을 확인합니다.
   운영에서 시스템 시계를 변경하여 48시간을 시험하지 않습니다. 격리된 시험 앱의 주입 시계만 사용합니다.

현재 SQLite 구현은 단일 호스트·로컬 디스크·단일 워커를 기준으로 합니다.
메모리에서 ZIP 검증/다운로드를 수행하므로 100 MiB 업로드 제한과 동시 요청 수에 맞는 메모리가 필요합니다.
로드 시험과 실제 최대 크기 파일 시험은 운영 용량 결정 전에 수행합니다.

## 보존·백업·복구와 롤백

- 보존 시작은 업로드 검증·파일 쓰기 완료 시각입니다. 정확히 48시간부터 다운로드를 거부합니다.
- 삭제 작업은 시작 시와 이후 300초 간격으로 실행합니다. 처리 시간·디스크 오류가 있으면 실제 삭제가 늦을 수 있지만 다운로드는 계속 거부합니다.
- 삭제 실패는 다음 주기에 재시도하며, 서버 중지 중 만료된 파일은 다음 시작에 정리합니다.
- `/var/lib/ai-blog/packages`와 프록시 임시 콘텐츠는 모든 백업·스냅샷·동기화에서 제외해야 합니다.
  제외할 수 없는 전체 디스크 스냅샷은 이 보존 정책과 양립하지 않습니다.
- `backup_metadata.py`로 메타데이터만 새 파일에 백업합니다. DB에는 기기 토큰 해시, FCM 토큰, 사용자 신고 게시글 URL도 포함되므로 접근을 제한합니다.
- 롤백은 서비스 중지 → 기존 승인 릴리스로 `current` 변경 → 서비스 시작 → health/인증 확인 순서입니다.
  이 변경은 기존 테이블을 파괴하지 않습니다. DB 복원이 필요하면 먼저 서비스를 중지하고 별도 복사본으로 검증합니다.
  메타데이터 복원으로 콘텐츠를 복원하지 않습니다. expires_at을 연장하거나 삭제된 ZIP을 백업에서 되살리지 않습니다.
- Windows·Android에 이미 내려받은 파일은 서버 삭제로 제거되지 않습니다.

승인 요청 시에는 대상 호스트/도메인, 릴리스 해시, 백업 제외 확인, 시험 결과, 서비스 중단 시간과 롤백 릴리스를 함께 제시합니다.
