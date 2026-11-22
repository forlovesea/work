# Ubuntu 서버 설치·사용 가이드

[개발 상세서](development-guide.md) · [Windows](windows-install-use.md) · [Android](android-install-use.md)

## 1. 서버의 역할과 준비물

서버는 Windows의 이벤트와 수동 발행용 ZIP을 받아 Android에 전달합니다.
FastAPI + SQLite를 사용하며 네이버 로그인·자동 발행을 대신하지 않습니다.

| 항목 | 요구사항 |
|---|---|
| Python | 3.10 이상 |
| 저장 공간 | 메타데이터 SQLite와 최대 48시간분 ZIP을 저장할 로컬 디스크 |
| 연결 | 시험은 루프백 HTTP, 원격 사용은 유효한 인증서의 HTTPS |
| 외부 서비스 | 기본 실행에는 필요 없음. 실제 FCM 사용 때만 Firebase 서비스 계정 |
| 실행 방식 | 단일 호스트·단일 Uvicorn 워커 권장 구성 |

이 프로젝트의 서버 코드는 Windows 로컬에서 검증했습니다. Ubuntu OS·systemd·Nginx·권한 설정은
대상 시험 서버에서 별도 검증해야 합니다. 아래 운영 설치 명령은 **승인된 호스트에서만** 수행합니다.

## 2. GitHub에서 소스 내려받기

아래 명령은 **Ubuntu 서버에 SSH로 접속한 터미널**에서 순서대로 실행합니다.
Windows에 있는 프로젝트 폴더를 서버에 미리 복사할 필요는 없습니다.
저장소는 `https://github.com/forlovesea/work.git`이며, 이 프로젝트는 저장소의
`AI_Blog_Auto_System_Phase1/ai-blog-auto-system` 하위에 있습니다.

### 2-1. Git과 Python 준비

```bash
sudo apt update
sudo apt install -y git ca-certificates curl python3 python3-venv
git --version
python3 --version
```

Python은 **3.10 이상**이어야 합니다. 3.10 미만이면 호환 Python과 해당 venv 모듈을
먼저 준비하고, 아래 `python3` 명령을 해당 인터프리터로 바꿉니다.

**기본 Python이 3.8인 환경:** `apt install python3`만으로 프로젝트 요구 버전이 되는 것은 아닙니다.
이미 Python 3.8로 설치하다 오류가 발생했다면 **8-2절의 복구 절차**를 순서대로 진행하세요.
시험 서버에서는 사용자 계정에 uv와 Python 3.11을 별도로 설치할 수 있습니다.
시스템 `/usr/bin/python3`는 교체하지 않습니다.

```bash
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/ai-blog-uv-install.sh
sh /tmp/ai-blog-uv-install.sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.11
```

프로젝트 루트로 이동한 뒤 아래 명령으로 가상환경을 만듭니다.
기존 `.venv`가 있다면 먼저 서버를 종료하고 보존용 이름으로 옮깁니다.

```bash
if command -v deactivate >/dev/null 2>&1; then deactivate; fi
if [ -d .venv ]; then mv .venv ".venv-backup-$(date +%Y%m%d-%H%M%S)"; fi
uv venv --python 3.11 --seed .venv
.venv/bin/python --version
.venv/bin/python -m pip install -r ubuntu-server/requirements.txt
```

이 경우 3절의 `python3 -m venv .venv`는 건너뜁니다. Python을 새로 설치해도 기존 3.8
가상환경은 자동으로 바뀌지 않습니다. 백업한 가상환경은 보존용이며 새 환경은 의존성을 다시 설치합니다.
uv가 설치한 Python은 사용자 홈에 있으므로 systemd 운영 배포 시에는 서비스 계정이 접근 가능한
별도 Python 설치 경로를 준비해야 합니다.
참고: [uv 설치](https://docs.astral.sh/uv/getting-started/installation/),
[Python 설치](https://docs.astral.sh/uv/guides/install-python/).

### 2-2. 저장소 다운로드와 프로젝트 폴더 이동

처음 설치하는 경우 일반 사용자 계정으로 실행합니다. `sudo git clone`은 사용하지 않습니다.

```bash
mkdir -p ~/src
cd ~/src
git clone https://github.com/forlovesea/work.git
cd work/AI_Blog_Auto_System_Phase1/ai-blog-auto-system
pwd
ls ubuntu-server/requirements.txt ubuntu-server/app/main.py shared/event-schema.json
git rev-parse HEAD
```

마지막 명령의 커밋 해시를 기록하면 어떤 소스로 검증했는지 확인할 수 있습니다.
이후 명령의 **프로젝트 루트**는 방금 이동한 `ai-blog-auto-system` 폴더를 뜻합니다.
GitHub에는 커밋·푸시된 파일만 있으므로 Windows에서만 수정한 내용은 내려받아지지 않습니다.

비공개 저장소라면 접근 권한이 있는 GitHub 계정의 PAT 또는 등록된 SSH 키가 필요합니다.
HTTPS 인증에서 비밀번호를 요구하면 계정 비밀번호 대신 PAT를 사용하며, 토큰을 URL에 넣지 않습니다.
SSH 키를 이미 등록했다면 clone 명령을 `git clone git@github.com:forlovesea/work.git`으로 바꿀 수 있습니다.

이미 `~/src/work`를 내려받았다면 다시 clone하지 않고 다음과 같이 이동합니다.
새 소스를 반영할 때는 실행 중인 시험 서버를 Ctrl+C로 종료한 뒤 진행합니다.

```bash
cd ~/src/work/AI_Blog_Auto_System_Phase1/ai-blog-auto-system
git status --short
git pull --ff-only
git rev-parse HEAD
```

로컬 수정이 있거나 pull이 실패하면 변경 사항을 먼저 확인합니다. 강제 초기화하지 않습니다.
업데이트 후에는 3절의 의존성 설치 명령을 다시 실행하고 서버를 재시작합니다.

### 2-3. 서버 압축 묶음으로 설치하는 경우 (선택)

위 GitHub 소스로 설치한다면 이 단계는 건너뛰고 **3절**로 이동합니다.
서버만 따로 옮길 때는 내려받은 프로젝트의 `release/2026-11-19/AI-Blog-Ubuntu-source.tar.gz`를 사용합니다.

```bash
mkdir -p ~/ai-blog-server
tar -xzf release/2026-11-19/AI-Blog-Ubuntu-source.tar.gz -C ~/ai-blog-server
cd ~/ai-blog-server
```

서버 묶음에는 `ubuntu-server`, `shared`, 설명 문서가 들어 있으며 Windows/Android 소스와 테스트 전체는 없습니다.
전체 통합 시험이나 앱 수정에는 Git 저장소를 사용하세요.

## 3. 격리된 시험 서버 실행

2절을 마친 프로젝트 루트에서 실행합니다. 처음 설치할 때 가상환경과 데이터 폴더를 준비합니다.

```bash
python3 -m venv .venv
.venv/bin/python -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required: recreate .venv using section 2-1"'
.venv/bin/python -m pip install -r ubuntu-server/requirements.txt
mkdir -p data/metadata data/packages
chmod 700 data data/metadata data/packages
```

이어서 **같은 터미널**에서 토큰과 데이터 경로를 설정하고 시작합니다.
생성된 토큰은 Windows 설정과 인증 시험에 사용할 수 있도록 개인 비밀 저장소에 보관합니다.
`printf`는 토큰 확인용이므로 화면을 공유하거나 출력 내용을 로그로 남기지 않습니다.

```bash
export BLOG_DEVICE_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf '%s\n' "$BLOG_DEVICE_TOKEN"
export BLOG_DB_PATH="$PWD/data/metadata/events.sqlite3"
export BLOG_PACKAGE_DIR="$PWD/data/packages"
export BLOG_PACKAGE_MAX_BYTES=104857600
.venv/bin/python -m uvicorn app.main:app --app-dir ubuntu-server --host 127.0.0.1 --port 8000 --workers 1
```

서버 프로세스는 이 터미널을 유지해야 동작합니다. Ctrl+C로 종료합니다.
임의 토큰을 새로 만들 때마다 Windows에 저장한 서버 토큰도 일치시켜야 합니다.
여기서 만든 환경변수는 새 터미널에 자동으로 전달되지 않습니다.

다른 터미널에서 상태를 확인합니다.

```bash
curl --fail http://127.0.0.1:8000/api/v1/health
```

`status: ok`가 나오면 기본 서버가 실행된 것입니다. 이 health API만으로 인증 성공을 확인한 것은 아닙니다.
인증이 필요한 API는 같은 토큰의 `X-Device-Token` 헤더를 사용합니다.

두 번째 Ubuntu 터미널에서 앞서 보관한 토큰을 입력하여 인증도 확인합니다.
입력은 화면에 표시되지 않습니다.

```bash
read -rsp '서버 토큰: ' BLOG_DEVICE_TOKEN; echo
export BLOG_DEVICE_TOKEN
curl --fail http://127.0.0.1:8000/api/v1/events?limit=1 \
  -H "X-Device-Token: $BLOG_DEVICE_TOKEN"
```

HTTP 200과 JSON 응답이면 인증 조회까지 성공한 것입니다. 401이면 서버를 시작할 때의 토큰과 비교합니다.
`127.0.0.1`은 Ubuntu 서버 내부에서만 접근할 수 있습니다. Windows/Android 연결은
5절과 7절의 HTTPS 구성을 마친 뒤 진행합니다.

### 종료 후 다시 실행

같은 터미널에서는 위 Uvicorn 명령만 다시 실행하면 됩니다. 새 SSH 세션에서는 다음과 같이
프로젝트 폴더로 이동하고 기존 토큰과 경로를 다시 설정합니다. 가상환경은 다시 만들 필요가 없습니다.
압축 묶음으로 설치했다면 첫 줄을 `cd ~/ai-blog-server`로 바꿉니다.

```bash
cd ~/src/work/AI_Blog_Auto_System_Phase1/ai-blog-auto-system
read -rsp '기존 서버 토큰: ' BLOG_DEVICE_TOKEN; echo
export BLOG_DEVICE_TOKEN
export BLOG_DB_PATH="$PWD/data/metadata/events.sqlite3"
export BLOG_PACKAGE_DIR="$PWD/data/packages"
export BLOG_PACKAGE_MAX_BYTES=104857600
.venv/bin/python -m uvicorn app.main:app --app-dir ubuntu-server --host 127.0.0.1 --port 8000 --workers 1
```

SSH 종료 후에도 계속 실행하거나 서버 재부팅 시 자동 실행하려면 7절의 systemd 배포 절차를 사용합니다.

Windows에서 서버 코드만 빠르게 시험할 경우에는 다음 명령을 사용할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r ubuntu-server/requirements.txt
$env:BLOG_DEVICE_TOKEN = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
$env:BLOG_DB_PATH = '.\data\metadata\events.sqlite3'
$env:BLOG_PACKAGE_DIR = '.\data\packages'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir ubuntu-server --host 127.0.0.1 --port 8000
```

## 4. 환경변수

| 이름 | 예시/기본값 | 설명 |
|---|---|---|
| `BLOG_DEVICE_TOKEN` | 기본 빈 값 | Windows/관리자 공유 토큰. 비어 있으면 관리자 API 거부 |
| `BLOG_DB_PATH` | `./blog_events.sqlite3` | SQLite 파일 경로 |
| `BLOG_PACKAGE_DIR` | DB 폴더 아래 `packages` | 외부 공개·백업에서 제외할 콘텐츠 저장 경로 |
| `BLOG_PACKAGE_MAX_BYTES` | `104857600` | ZIP 업로드 상한, 100 MiB |
| `BLOG_FCM_CREDENTIALS` | 미설정 | 실제 FCM 서비스 계정 JSON 경로 |

개발 시 `ubuntu-server/.env.example`을 `.env`로 복사할 수도 있습니다.
`.env`와 비밀 파일은 Git에 올리지 않습니다. 운영에서는 별도 권한 제한 환경파일을 사용합니다.
파일 저장 루트를 웹 서버의 static/alias 디렉터리로 연결하지 않습니다.

## 5. Windows 연결 및 Android 페어링

원격 앱 연결 전에 **[HTTPS 설정 절차](https-setup.md)**를 완료하세요. 인증서 최초 발급부터 Nginx 적용·갱신까지 설명합니다. Uvicorn의 HTTP 8000 포트를 앱의 HTTPS 주소로 지정하면 연결되지 않습니다.

### Windows

Windows 설정에 서버 URL과 관리자 토큰을 넣고 **서버 연결 → 연결 / 이벤트 조회**를 누릅니다.
서로 다른 PC/서버라면 HTTPS 도메인을 사용합니다. Windows의 `localhost`는 Windows 자신의 주소입니다.

### Android

관리자 토큰을 사용할 수 있는 터미널에서 코드 발급 API를 호출합니다.

```bash
curl --fail -X POST http://127.0.0.1:8000/api/v1/pairing/codes \
  -H "X-Device-Token: $BLOG_DEVICE_TOKEN"
```

응답의 `code`를 10분 안에 Android 설정에 입력합니다. 한 번만 사용할 수 있습니다.
Android는 별도의 90일 기기 토큰을 받으므로 관리자 토큰을 앱에 입력하지 않습니다.
등록 기기는 관리자 인증으로 조회·폐기할 수 있습니다.

```bash
curl --fail http://127.0.0.1:8000/api/v1/devices \
  -H "X-Device-Token: $BLOG_DEVICE_TOKEN"
# 아래 ID를 실제 폐기할 기기 ID로 바꾼 뒤에만 실행
curl --fail -X DELETE http://127.0.0.1:8000/api/v1/devices/DEVICE_UUID \
  -H "X-Device-Token: $BLOG_DEVICE_TOKEN"
```

같은 서버에 페어링한 기기들은 콘텐츠와 이력을 공유합니다. 사용자별 테넌트 격리는 없습니다.

## 6. 콘텐츠 수명 주기

```text
Windows ZIP 생성 → 인증 업로드 → 무결성 검사·저장 완료
                                └─ 여기서부터 48시간
                                      ↓ 남은 6시간 / 1시간 알림
                                정확한 만료 시각: 다운로드 410
                                      ↓ 다음 정리 주기
                                파일 삭제 + PACKAGE_DELETED 이벤트
```

서버는 시작할 때와 이후 300초 간격으로 유지관리 작업을 수행합니다.
삭제 오류가 발생하면 다음 주기에 재시도합니다. 삭제가 늦어져도 만료 파일 다운로드는 허용하지 않습니다.
동일 UUID·동일 ZIP 재전송은 기존 결과를 반환하고 보존 기간을 연장하지 않습니다.
동일 UUID에 다른 내용은 409, 만료된 UUID 재업로드는 410입니다.

다운로드 유형: ZIP 기본, `kind=html|txt|docx|manifest|image`. 이미지에는 `image_index`를 사용합니다.
응답의 `X-Content-SHA256`과 bytes를 비교하여 무결성을 확인합니다.
다운로드한 PC/휴대폰의 파일은 서버 만료·삭제와 별도로 남습니다.

## 7. 운영 배포·백업·로그

[빌드·배포 문서](build-and-deploy.md)에 서비스 계정, `/opt/ai-blog/current`, systemd, TLS 프록시,
백업 제외, 재시작, 롤백 순서가 있습니다. 제공 파일은 다음과 같습니다.

- `ubuntu-server/deploy/ai-blog.service`: 단일 워커·비특권 계정 서비스 예시
- `ubuntu-server/deploy/nginx.conf.example`: HTTPS/WS 프록시, 업로드·응답 버퍼/캐시 비활성 예시
- `ubuntu-server/backup_metadata.py`: 콘텐츠를 복사하지 않는 SQLite 메타데이터 백업
- `ubuntu-server/backup-excludes.txt`: 콘텐츠 제외 정책 참고

서비스 설치 후 `systemctl status ai-blog`, `journalctl -u ai-blog`로 상태·오류를 확인합니다.
토큰·API 키·글 본문을 로그에 추가하지 않습니다. FCM 등록 토큰과 게시글 신고 URL은 DB에 있으므로 백업도 제한합니다.
전체 디스크 스냅샷에 콘텐츠가 포함된다면 48시간 보존 정책을 충족하지 못합니다.

## 8. 오류 해결

| 응답/증상 | 의미 | 조치 |
|---|---|---|
| `dict[str, Any]`에서 `TypeError: 'type' object is not subscriptable` | Python 3.8 가상환경 사용 | 아래 8-2절의 Python 3.8 → 3.11 복구 절차 실행 |
| `git: command not found` | Git 미설치 | 2-1절 패키지 설치 실행 |
| clone 시 `Repository not found` / 인증 실패 | 저장소 주소 또는 접근 권한 문제 | 주소와 GitHub 계정 권한, PAT/SSH 인증 확인 |
| `destination path 'work' already exists` | 이미 내려받은 폴더 존재 | 2-2절의 기존 저장소 이동·갱신 절차 사용 |
| `requirements.txt`를 찾을 수 없음 | 실행 폴더 오류 | 2-2절의 프로젝트 하위 경로로 이동 |
| `No module named venv` / `ensurepip` 오류 | venv 패키지 누락 | 사용 중인 Python 버전에 맞는 venv 패키지 설치 |
| `[Errno 98] address already in use` | 지정한 포트 사용 중 | 아래 8-1절에서 기존 프로세스 확인 또는 시험 포트 변경 |
| 401 | 토큰 없음·불일치·만료·폐기 | Windows 토큰 확인 또는 Android 재페어링 |
| 409 | 같은 UUID에 다른 ZIP/완료 URL | 기존 결과 확인, 새 콘텐츠는 새 ID 사용 |
| 410 | 콘텐츠 만료 | 새 초안·새 패키지 생성 |
| 413 | 서버 파일 상한 초과 | 이미지 크기/개수 줄이기 |
| 415/422 | 파일 형식·해시·manifest·요청 형식 오류 | 원본 앱에서 다시 생성, 파일 수동 수정 금지 |
| 503 | 파일 없음·손상 등 | 서버 디스크·권한·로그 확인 |
| health 성공, 앱 실패 | 인증·주소·TLS·Wi-Fi 정책 문제 가능 | 앱이 사용하는 실제 주소와 토큰 확인 |
| WS만 끊김 | 프록시 Upgrade/timeout 설정 | 제공 Nginx 예시와 비교 |
| 만료 파일이 남음 | 정리 주기 대기·서비스 중지·삭제 오류 | 로그와 권한 확인; 다운로드는 계속 차단되어야 함 |

실제 FCM 설정은 [Android 가이드](android-install-use.md)의 선택 설정을 참고하세요.

### 8-1. 8000 포트 충돌 해결

다음 로그가 나오면 다른 프로세스가 이미 `127.0.0.1:8000`을 사용하고 있습니다.
`Application startup complete`가 앞에 나오더라도, 이후 바인딩 오류와 종료 로그가 나오면
이번에 실행한 서버는 종료된 상태입니다.

```text
ERROR: [Errno 98] error while attempting to bind on address ('127.0.0.1', 8000): address already in use
```

먼저 Ubuntu 서버 터미널에서 기존 응답과 포트를 점유한 프로세스를 확인합니다.

```bash
curl --fail http://127.0.0.1:8000/api/v1/health
sudo ss -ltnp 'sport = :8000'
```

- `"status":"ok"` 응답이면 기존 서버가 실행 중일 수 있습니다. `ss`의 프로세스 이름과 PID도 확인합니다.
  응답만으로 방금 실행한 소스 버전이 서비스 중이라고 판단하지 않습니다.
- 앞서 직접 실행한 이 프로젝트 서버라면 해당 터미널에서 **Ctrl+C**로 종료한 뒤 3절의 명령으로 다시 실행합니다.
- systemd로 설치한 서버라면 `systemctl status ai-blog`로 확인합니다. 실행 중인 서비스를 이용할 경우
  별도 Uvicorn을 중복 실행하지 않습니다.
- 다른 프로그램이 사용하는 포트라면 해당 프로세스를 임의로 종료하지 말고, 시험 서버 포트를 변경합니다.

**8001 포트로 시험 실행:** 프로젝트 루트에서 3절의 토큰·데이터 경로 환경변수를 설정한 상태로 실행합니다.

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir ubuntu-server --host 127.0.0.1 --port 8001 --workers 1
```

다른 SSH 터미널에서 변경한 포트의 상태를 확인합니다.

```bash
curl --fail http://127.0.0.1:8001/api/v1/health
```

`"status":"ok"` 응답을 확인한 다음, 3절의 인증 조회도 URL의 포트를 `8001`로 바꾸어 수행합니다.
8001도 사용 중이면 같은 방식으로 점유 프로세스를 먼저 확인합니다.

포트를 변경하면 이후 로컬 API 호출과 페어링 명령에도 `8001`을 사용합니다.
Nginx를 사용하는 경우 upstream의 `proxy_pass` 대상 포트를 맞추고, systemd로 계속 실행하려면
서비스의 Uvicorn `--port`도 맞춥니다. HTTPS 프록시 뒤의 Windows/Android 앱은 기존 HTTPS URL을
사용하며, 내부 포트 번호를 앱 URL에 추가하지 않습니다.
`127.0.0.1` 바인딩은 그대로이므로 포트 변경만으로 외부 PC에서 직접 접속할 수 있게 되지는 않습니다.

### 8-2. Python 3.8 오류와 Python 3.11로 전환

서버 실행 시 다음 위치에서 실패하고 traceback 경로에 `python3.8`이 표시되면,
Python 3.8로 만든 가상환경을 사용 중인 것입니다.

```text
File ".../ubuntu-server/app/main.py", line 37, in Event
    payload: dict[str, Any] = Field(default_factory=dict)
TypeError: 'type' object is not subscriptable
```

Python 3.8은 이 `dict[str, Any]` 타입 표기를 처리하지 못합니다. 프로젝트의 최소 요구 버전은
Python 3.10이며, 아래 절차는 Python 3.11로 환경을 다시 만듭니다.
Python만 새로 설치하거나 기존 `.venv`에서 pip 패키지만 갱신해도 가상환경의 Python 버전은 바뀌지 않습니다.

**1. 현재 프로젝트 폴더에서 가상환경 버전 확인**

GitHub에서 내려받은 `AI_Blog_Auto_System_Phase1/ai-blog-auto-system` 폴더로 이동합니다.
설치 경로를 다르게 지정했다면 실제 경로를 사용합니다.

```bash
pwd
.venv/bin/python --version
```

`Python 3.8.x`라면 아래 단계를 진행합니다. 실행 중인 시험 서버가 있다면 먼저 해당 터미널에서 Ctrl+C로 종료합니다.

**2. 사용자 계정에 Python 3.11 설치**

```bash
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/ai-blog-uv-install.sh
sh /tmp/ai-blog-uv-install.sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.11
```

시스템의 `/usr/bin/python3`는 변경하지 않습니다. uv가 이미 설치되어 있다면 설치 스크립트 실행은 생략할 수 있습니다.

**3. 기존 가상환경 보존 후 Python 3.11 가상환경 생성**

프로젝트 루트에서 실행합니다. 데이터 폴더와 소스는 그대로 두고 `.venv`만 보존용 이름으로 옮깁니다.

```bash
if command -v deactivate >/dev/null 2>&1; then deactivate; fi
if [ -d .venv ]; then mv .venv ".venv-backup-$(date +%Y%m%d-%H%M%S)"; fi
uv venv --python 3.11 --seed .venv
.venv/bin/python --version
.venv/bin/python -m pip install -r ubuntu-server/requirements.txt
```

버전 출력이 **`Python 3.11.x`**인지 확인합니다. 이후 `python3 -m venv .venv`로 다시 만들지 않습니다.
FCM을 사용하던 환경이라면 `.venv/bin/python -m pip install -r ubuntu-server/requirements-fcm.txt`도 실행합니다.

**4. 환경변수 설정 후 서버 재실행**

같은 터미널에 기존 토큰이 남아 있으면 그대로 사용합니다. 없다면 입력 요청에 기존 토큰을 넣습니다.
아직 토큰을 만들지 않았다면 3절의 토큰 생성 절차를 먼저 진행합니다.

```bash
if [ -z "$BLOG_DEVICE_TOKEN" ]; then
  read -rsp '기존 서버 토큰: ' BLOG_DEVICE_TOKEN; echo
fi
export BLOG_DEVICE_TOKEN
mkdir -p data/metadata data/packages
chmod 700 data data/metadata data/packages
export BLOG_DB_PATH="$PWD/data/metadata/events.sqlite3"
export BLOG_PACKAGE_DIR="$PWD/data/packages"
export BLOG_PACKAGE_MAX_BYTES=104857600
.venv/bin/python -m uvicorn app.main:app --app-dir ubuntu-server --host 127.0.0.1 --port 8000 --workers 1
```

기존 DB와 패키지 저장 경로를 별도로 지정했다면 위 기본 경로 대신 기존 값을 사용합니다.
`[Errno 98] address already in use`가 발생하면 **8-1절**을 따라 포트를 확인합니다.
8001로 변경했다면 아래 확인 명령도 8001로 바꿉니다.

**5. 다른 SSH 터미널에서 확인**

```bash
curl --fail http://127.0.0.1:8000/api/v1/health
```

`"status":"ok"` 응답이면 기본 실행 확인이 끝났습니다. 이어서 3절의 토큰 인증 조회를 수행합니다.
이 절차는 사용자 계정으로 실행하는 시험 서버용이며, systemd 배포 시 Python 경로와 서비스 계정 접근 권한은
2-1절과 7절을 함께 확인합니다.
