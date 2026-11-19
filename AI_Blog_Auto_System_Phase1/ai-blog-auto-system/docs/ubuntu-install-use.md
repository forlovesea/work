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

## 2. 소스 준비

전체 저장소를 사용할 경우:

```bash
git clone https://github.com/forlovesea/work.git
cd work/AI_Blog_Auto_System_Phase1/ai-blog-auto-system
```

서버만 설치할 경우 `release/2026-11-19/AI-Blog-Ubuntu-source.tar.gz`를 빈 릴리스 폴더에 풉니다.

```bash
mkdir ai-blog-server
tar -xzf AI-Blog-Ubuntu-source.tar.gz -C ai-blog-server
cd ai-blog-server
```

서버 묶음에는 `ubuntu-server`, `shared`, 설명 문서가 들어 있으며 Windows/Android 소스와 테스트 전체는 없습니다.
전체 통합 시험이나 앱 수정에는 Git 저장소를 사용하세요.

## 3. 격리된 시험 서버 실행

Ubuntu에 Python과 venv 모듈이 없다면 승인된 시험 환경에서 설치합니다.

```bash
sudo apt update
sudo apt install python3 python3-venv
python3 --version
```

출력 버전이 3.10 미만이면 호환 Python을 먼저 준비하세요. 이어서 프로젝트 루트에서 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r ubuntu-server/requirements.txt
mkdir -p data/metadata data/packages
chmod 700 data data/metadata data/packages
export BLOG_DEVICE_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
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
