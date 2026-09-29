# Git checkout 후 환경 재현

이 프로젝트는 `https://github.com/forlovesea/work` 저장소의 `BatteryWatch/` 하위에 있습니다.
프로그램·이미지·음원·테스트·의존성 잠금 파일·Gradle Wrapper를 Git으로 복원합니다.
토큰, 인증서 개인 키, 현장 프로필과 측정 DB는 별도 보관 자료이며 Git에 포함하지 않습니다.

## Ubuntu 서버

```bash
git clone https://github.com/forlovesea/work.git /home/jihyun/work
cd /home/jihyun/work/BatteryWatch
/home/jihyun/.local/bin/uv run --python 3.12 python bootstrap.py server --test
```

Python 3.12가 이미 있으면 마지막 명령 대신 `python3.12 bootstrap.py server --test`를 사용합니다. Ubuntu의 기본 Python을 교체할 필요는 없습니다.
생성된 실행기는 `server/.venv/bin/python`입니다.

FCM 사용 시:

```bash
/home/jihyun/.local/bin/uv run --python 3.12 python bootstrap.py server --with-push --test
```

`server/requirements-push.lock.txt`의 모든 버전을 사용합니다. 자격증명 없이 라이브러리 설치와 로컬 테스트가 가능하지만 실제 FCM 발송에는 운영 설정이 필요합니다.

기존 서버 이전은 보관한 `server/*.local.json`, 데이터베이스와 인증서를 먼저 복원합니다. 기존 파일이 있으면 `init`을 실행하지 않습니다.
처음 구성할 때만 다음을 실행합니다.

```bash
cd server
.venv/bin/python server.py init --site site-01 --device battery-01
.venv/bin/python server.py enable-api --site site-01 --device battery-01
.venv/bin/python server.py doctor
```

인증서 경로와 바인딩 설정을 적용한 뒤 `sh run.sh`로 실행합니다. 이 문서는 서비스 자동 등록이나 방화벽 변경을 수행하지 않습니다.
Ubuntu에 이미 발급된 인증서는 `/etc/letsencrypt/live/batterywatch-ip/`에 그대로 유지합니다.

## Windows 현장 수집기

기존 SNMP 라이브러리가 `asyncore`를 사용하므로 **Python 3.10**으로 설치합니다. Python 3.12 서버 환경과 합치지 않습니다.

```powershell
cd <checkout 경로>\BatteryWatch
py -3.10 bootstrap.py client --test
.\monitoring-client\run.bat
```

`monitoring-client/requirements-lock.txt`는 직접/간접 의존성 19개의 버전을 고정합니다.
프로필이 없으면 앱에서 장비 IP, GET/SET/Trap community와 업로드 접속 값을 입력하세요.
반복 사용하는 초기값은 `device-defaults.example.json`을 `device-defaults.local.json`으로 복사해 설정할 수 있습니다. 이 로컬 파일은 Git에서 제외됩니다. 기존 프로필 값이 초기값보다 우선합니다.

## Android

- JDK 17 (Windows 도구 설치 스크립트는 Microsoft JDK 17.0.20.1 고정)
- Android SDK platform 35, build-tools 35.0.0
- Gradle 8.11.1: 저장소의 Wrapper가 체크섬을 검증해 내려받음

Windows에서 도구를 준비하려면 `android-app`에서 `python setup_tools.py`를 실행합니다.
`.toolchain/java/` 안의 JDK 폴더를 `JAVA_HOME`, `.toolchain/sdk`를 `ANDROID_HOME`으로 설정합니다. 기존 JDK/SDK 또는 Android Studio 설치를 사용해도 됩니다.
SDK Manager로 `platforms;android-35`, `build-tools;35.0.0`을 설치하고 라이선스에 동의해야 합니다.

```powershell
cd android-app
.\gradlew.bat --no-daemon :app:assembleOfflineDebug :app:testOfflineDebugUnitTest
```

Linux에서는 같은 인자로 `sh gradlew`를 실행합니다.
조회 APK는 `app/build/outputs/apk/offline/debug/app-offline-debug.apk`에 생성됩니다. `dist/`의 로컬 APK와 빌드 도구/캐시는 Git에 포함하지 않습니다.
Windows는 `C:\src\work`처럼 짧은 checkout 경로를 권장합니다. 긴 경로에서는 Gradle 캐시 변환이 실패할 수 있습니다.
푸시 APK는 실제 `app/google-services.json`을 복원한 뒤 `:app:assemblePushDebug`로 빌드합니다.
debug 서명 키는 PC마다 생성되므로 다른 PC의 APK로 기존 앱을 업데이트하려면 같은 키를 별도 복원해야 합니다. 키는 Git에 넣지 않습니다.

## 별도로 복원할 로컬 자료

| 자료 | 위치 |
|---|---|
| 서버 설정·업로드·조회 토큰 | `server/*.local.json` |
| 서버 측정·알람 이력 | `server/data/*.sqlite3` 또는 설정에서 지정한 DB 경로 |
| 수집기 프로필·업로드 설정 | `monitoring-client/profiles/` (앱 실행 위치에 따라 다른 기존 profiles 폴더도 확인) |
| 수집기 초기 접속 값 | `monitoring-client/device-defaults.local.json` |
| 수집기 미전송 큐 | `monitoring-client/data/` |
| Android Firebase 설정 | `android-app/app/google-services.json` |
| 서비스 계정·TLS 인증서·서명 키 | 운영 호스트의 별도 보관 위치 |

DB는 실행 중인 파일을 단순 복사하지 말고 서버의 `backup` 명령이나 SQLite 백업 API를 사용합니다.
수집기 미전송 큐 이름은 프로필의 절대 경로에 연결되어 있습니다. 이전 전 큐 전송을 완료하거나 기존 절대 경로를 유지해야 같은 큐를 이어서 사용할 수 있습니다.
로컬 백업에는 비밀 값이 들어 있으므로 Git에 추가하지 말고 별도로 안전하게 전달하세요.

## 확인 명령

```bash
server/.venv/bin/python server/server.py self-test
server/.venv/bin/python server/server.py doctor
```

`self-test`는 운영 자격증명 없이 전체 연동을 시험합니다. `doctor`는 복원된 운영 설정을 확인합니다.
동일한 실행 환경은 위 버전과 설정으로 재구성하며, OS·CPU·서명 키가 다른 빌드의 파일 해시까지 동일함을 의미하지 않습니다.
