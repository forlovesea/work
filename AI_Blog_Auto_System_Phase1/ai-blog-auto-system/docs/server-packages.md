# Phase 4: 수동 발행 패키지 서버

기존 FastAPI/SQLite 이벤트 서버에 구현했습니다. 운영 서버에 배포하지 않았습니다.
Windows 출력 기능이 만든 format_version 1.0 ZIP을 그대로 업로드합니다.
HTML, TXT, 이미지 내장 DOCX, PNG 이미지, manifest.json을 단일 비공개 ZIP에 저장하며
서버 디스크에 압축을 풀거나 공개 정적 파일 URL을 만들지 않습니다.

## API

모든 요청에 `X-Device-Token: <BLOG_DEVICE_TOKEN>`이 필요합니다. 빈 토큰은 거부합니다.
Phase 5에서 Windows/관리자는 기존 공유 토큰을 유지하고, Android는 일회용 페어링으로 받은
90일 읽기 전용 기기 토큰을 사용합니다. 업로드는 관리자 토큰만 허용합니다.
조회·다운로드는 관리자 또는 유효한 Android 토큰을 허용하며 만료·폐기를 검사합니다.
같은 서버에 등록된 기기는 동일 패키지를 공유합니다. 사용자별 테넌트 격리는 없습니다.
[Android 페어링 안내](../android-app/README.md)를 참조하세요.

| 요청 | 동작 |
|---|---|
| POST /api/v1/packages | application/zip 원시 본문, X-Content-SHA256에 ZIP의 소문자 SHA-256 필수 |
| GET /api/v1/packages | 최신 메타데이터 최대 100개, 본문·서버 경로 미포함 |
| GET /api/v1/packages/{UUID}/download | 원본 ZIP 다운로드 |
| 위 URL에 ?kind=html 또는 txt/docx/manifest | 해당 파일 다운로드 |
| 위 URL에 ?kind=image&image_index=0 | manifest.image_order 기준 0부터 시작하는 이미지 다운로드 |

응답 메타데이터는 package_id(콘텐츠 UUID), sha256, size, uploaded_at, expires_at,
deleted_at입니다. 업로드 응답은 new도 포함합니다. 같은 UUID/동일 ZIP 재전송은 new=false,
보존 시각을 연장하지 않습니다. 같은 UUID/다른 ZIP은 409이며, 동일 ZIP도 만료 후에는 410입니다.
이미 만료된 콘텐츠를 다시 보관하려면 새 콘텐츠 UUID로 새 패키지를 만들어야 합니다.
UUID 중복 판정을 위해 본문 없는 메타데이터를 삭제 후에도 보관합니다.

인증 실패 401, 없는 UUID/이미지 404, 만료 410, 용량 초과 413, MIME 오류 415,
ZIP/해시/경로/manifest/형식 오류 422입니다. 저장 파일 유실·변조는 503으로 거부합니다.
다운로드는 attachment, no-store, nosniff이며 HTML도 서버에서 실행하거나 미리보기로 제공하지 않습니다.
개별 HTML 다운로드의 상대 이미지 경로는 ZIP을 함께 풀었을 때 연결됩니다.
서버는 외부 링크를 가져오지 않습니다. 업로드 형식 검증은 악성코드 백신 검사가 아닙니다.

PowerShell 업로드 예시(토큰은 환경변수로 제공):

```powershell
$zip = 'C:\exports\manual-package.zip'
$sha = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
$headers = @{ 'X-Device-Token' = $env:BLOG_DEVICE_TOKEN; 'X-Content-SHA256' = $sha }
$result = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/packages' -Method Post -ContentType 'application/zip' -Headers $headers -InFile $zip
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/packages/$($result.package_id)/download" -Headers @{ 'X-Device-Token' = $env:BLOG_DEVICE_TOKEN } -OutFile 'downloaded.zip'
```

GUI 업로드 버튼 연결은 미구현입니다. Android 클라이언트는 후속 Phase 5에서 추가했습니다.

## 보존·알림·삭제

- 파일 검증과 전체 기록/fsync 완료 후, 최종 DB 트랜잭션에서 UTC uploaded_at을 기록합니다.
  expires_at = uploaded_at + 48시간입니다. 클라이언트 created_at/packaged_at은 보존 시각에 사용하지 않습니다.
- 다운로드 시작 전과 파일 읽기/무결성 검증 후 현재 시각을 다시 확인합니다.
  현재 시각 >= expires_at이면 정리 작업이 실행되기 전이라도 410입니다.
  만료 전에 이미 전송을 시작한 응답이나 사용자가 내려받은 복사본을 회수하지는 않습니다.
- FastAPI lifespan에서 시작 시 한 번, 이후 300초마다 정리 작업을 수행합니다.
  정상 실행 중 물리 삭제 지연은 주기 5분에 작업 실행 시간이 더해집니다.
  서버가 중지되었으면 다음 시작 때 정리하며, 삭제 실패는 로그 후 다음 주기에 재시도합니다.
- PACKAGE_UPLOAD_SUCCESS, PACKAGE_EXPIRING_6H, PACKAGE_EXPIRING_1H, PACKAGE_DELETED를
  기존 이벤트 테이블에 기록합니다. 기존 `/api/v1/events?after=...` API로 수신합니다.
  외부 푸시/FCM은 구현하지 않았습니다.
- 6시간/1시간 임계치를 지난 첫 정리 작업에서 각 이벤트를 한 번 기록합니다(정상 실행 중 최대 약 5분 지연).
  재시작으로 두 임계치를 모두 지났지만 아직 유효하면 두 이벤트를 따라잡아 기록하고,
  이미 만료됐으면 사전 알림 없이 삭제만 처리합니다.
- 이벤트 UUID와 DB 트랜잭션으로 여러 프로세스·재시작에서도 이벤트 중복을 방지합니다.
  삭제 후 DB 커밋 전 중단되면 다음 실행에서 파일 부재를 성공으로 처리합니다.
- 만료 ZIP 한 개를 삭제하면 안의 HTML/DOCX/TXT/이미지도 함께 사라집니다.
  업로드 파일 기록 중 중단되어 메타데이터 없이 남은 서버 생성 ZIP도 정리합니다.
  SSD 덮어쓰기 보안 삭제나 외부 저장소 스냅샷 제거를 수행한다는 의미는 아닙니다.

## 제한과 경로 방어

기본 업로드 100 MiB, ZIP 해제 크기 총 120 MiB, 구성 파일 최대 34개(이미지 30개)입니다.
manifest 256 KiB, PNG 20 MiB/24 MP, DOCX 내부 200개 항목/64 MiB 한도입니다.
Content-Length와 실제 스트림 바이트 수를 모두 검사합니다. 요청 본문과 다운로드를 메모리에서
처리하므로 프로세스 동시 요청 수와 메모리 용량을 함께 제한해야 합니다.

허용 파일 이름은 고정 4개와 images/thumbnail.png, images/body_XX.png뿐입니다.
절대 경로, 상위 경로, 역슬래시, 드라이브 경로, 중복 항목, 심볼릭 링크, 암호화 ZIP,
허용하지 않은 압축 방식, 미등록 파일을 거부합니다. ZIP CRC, manifest 크기/해시,
PNG 청크 CRC/구조, DOCX ZIP/XML 구조도 검증합니다. DOCX 매크로, 임베디드 개체,
외부 이미지/리소스를 거부하며 일반 출처 하이퍼링크는 허용합니다.

원본 파일명·제목을 디스크 경로에 사용하지 않습니다. 서버가 만든 난수 파일명과
고정 저장 루트만 사용하며 다운로드 URL은 UUID와 허용된 kind/index만 받습니다.
파일 권한은 POSIX 0600, 새 저장 디렉터리는 0700으로 생성합니다.
기존 디렉터리와 상위 디렉터리도 서비스 계정만 쓸 수 있게 관리해야 합니다.
Windows에서는 서비스 계정 ACL을 별도로 적용합니다.

## Ubuntu 실행 설정(배포용 안내, 현 서버 미적용)

Python 3.10 이상 구문을 사용합니다. 권장 Python 3.11에서 가상환경을 만들고
`ubuntu-server/requirements.txt`를 설치합니다. 이 세션의 실행 검증은 Windows Python 3.10.11이며
실제 Ubuntu 서비스/파일 권한 검증은 별도로 필요합니다.

```bash
export BLOG_DB_PATH=/var/lib/ai-blog/metadata/events.sqlite3
export BLOG_PACKAGE_DIR=/var/lib/ai-blog/packages
export BLOG_PACKAGE_MAX_BYTES=104857600
# BLOG_DEVICE_TOKEN은 권한 0600 환경파일/서비스 비밀정보로 설정
.venv/bin/python -m uvicorn app.main:app --app-dir ubuntu-server --host 127.0.0.1 --port 8000 --limit-concurrency 4
```

공개 접속에는 HTTPS 리버스 프록시를 사용하고 패키지 디렉터리를 alias/static으로 연결하지 않습니다.
프록시의 업로드/응답 디스크 버퍼와 캐시는 꺼야 임시 복제본이 별도 위치에 남지 않습니다.
예: 해당 API location에 `client_max_body_size 100m; proxy_request_buffering off; proxy_buffering off; proxy_cache off;`.
서비스는 상시 실행·자동 재시작하도록 구성하고 시계를 동기화해야 합니다.
SQLite의 쓰기 직렬화를 이용하므로 현재 구현은 단일 호스트의 로컬 디스크용입니다.
PostgreSQL/분산 저장소 마이그레이션은 미포함입니다.

## 백업 제외 정책

콘텐츠 루트, 프록시 임시 파일, 테스트 출력물, 다운로드 복사본을 서버 백업/동기화/스냅샷에서 제외합니다.
패키지 볼륨은 파일시스템·VM 전체 스냅샷 대상에서도 제외해야 합니다.
다른 경로로 `BLOG_PACKAGE_DIR`을 바꿀 때는 백업 제외 목록도 함께 수정해야 합니다.
`ubuntu-server/backup-excludes.txt`는 기본 경로용 tar 제외 템플릿이며 외부 백업 도구를 자동 변경하지 않습니다.

제공하는 백업 도구는 디렉터리를 순회하지 않고 SQLite 메타데이터만 복사합니다:

```bash
.venv/bin/python ubuntu-server/backup_metadata.py /var/lib/ai-blog/metadata/events.sqlite3 /secure-backups/events-20261118.sqlite3
```

대상은 새 파일이어야 하며 0600으로 생성합니다. 실행 중인 SQLite는 backup API로 일관되게 복사합니다.
DB에는 패키지 본문/이미지/ZIP이 없고 UUID·해시·크기·시각·상태와 감사 이벤트만 저장합니다.
Phase 5의 기기 토큰 해시와 FCM 등록 토큰도 메타데이터 DB에 있으므로 백업 권한을 제한합니다.
이벤트 payload에도 본문, API 키, 비밀번호, 쿠키를 넣지 마세요.
다운로드 이력은 package_downloads에 UUID·kind·시각만 기록합니다.
메타데이터 복원만으로 콘텐츠를 복원할 수 없으며, 복구 후에도 expires_at을 기준으로 거부합니다.
이 정책은 사용자 PC에 이미 다운로드된 파일을 삭제하지 않습니다.
