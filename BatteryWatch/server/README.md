# 축전지 데이터 서버

장비 없이 시작하려면 `demo.bat`을 실행하세요. 전체 연동 자동 검증은 `python server.py self-test`, 운영 설정 점검은 `python server.py doctor`입니다. [로컬 데모와 앱 연결 안내](../docs/local-demo.md).

클라이언트의 [TCP 프로토콜](../docs/tcp-upload-protocol.md)에 맞춘 TCP/TLS 수신·저장 서버입니다. **Python 3.10 이상**에서 실행합니다. 조회/등록 API, 알람 판정·복구·확인 기록, FCM 발송 큐도 구현했습니다. FCM 사용 시에만 `requirements-push.txt`의 추가 패키지가 필요합니다.

## 바로 실행 (같은 PC에서 연결 시험)

```powershell
cd C:\Users\Administrator\Downloads\proj\GITHUB\work\BatteryWatch\server
python server.py init --site site-01 --device battery-01
python server.py check
python server.py run
```

`init`은 최초 한 번 실행합니다. 이미 있는 설정이나 토큰은 덮어쓰지 않습니다. 실행 중지는 Ctrl+C입니다. 초기화 후에는 `run.bat`으로 실행해도 됩니다.

- `server.local.json`: 서버 설정, 클라이언트별 토큰 SHA256와 허용 현장/장비
- `client-connection.local.json`: **클라이언트에 입력할 실제 토큰**과 접속 설정
- `data/batterywatch.sqlite3`: 수신 데이터 DB (최초 run 때 생성)
- `logs/server.log`: 접속·저장·거부·종료 기록 (5 MiB × 최대 6개 파일)

초기 설정은 `127.0.0.1:9443`, TLS 꺼짐입니다. 모니터링 클라이언트의 **서버 TCP 업로드 설정**에서 `client-connection.local.json`의 값을 입력하고 업로드를 켜면 됩니다. 기본 5초 간격 snapshot과 Trap 이벤트가 저장됩니다. 클라이언트 IP와 장비의 SNMP IP는 서로 다른 설정입니다.

## 저장 확인 및 백업

서버 실행 중 별도 터미널에서:

```powershell
python server.py inspect --limit 10
python server.py inspect --site site-01 --device battery-01 --limit 5
python server.py backup backups/batterywatch-20260928.sqlite3
```

inspect 결과는 전체 저장 건수, 장비별 최신 snapshot, 최근 메시지 원문과 최근 접속 세션입니다. 세션의 disconnected_at이 null이면 서버 기준 연결 중이며 last_seen_at은 마지막 저장/중복 수신 확인 시각입니다. 급격한 네트워크 단절은 소켓 오류나 타임아웃 때 반영됩니다. 서버 재실행 시 이전 미종료 세션을 종료 상태로 정리합니다.

backup은 실행 중인 DB에서도 SQLite 백업 API로 일관된 사본을 만듭니다. 기존 파일은 덮어쓰지 않습니다. WAL 모드이므로 실행 중 DB 파일 하나만 복사하지 마세요. 복구 시 서버를 중지하고 백업을 **새 경로**에 복사한 다음 설정의 database를 해당 경로로 변경해 재시작합니다.

## 공인 IP 서버 설정

1. 실제 서버에서 `init`을 실행해 운영용 토큰을 새로 생성합니다.
2. 서버 이름 또는 공인 IP와 일치하는 인증서를 준비합니다. IP로 접속하면 인증서 SAN에 해당 IP가 있어야 합니다.
3. `server.local.json`의 host를 `0.0.0.0`으로 바꾸고 tls에 PEM 인증서/키를 지정합니다.

```json
"tls": {
  "certfile": "certs/fullchain.pem",
  "keyfile": "certs/privkey.pem"
}
```

4. 방화벽/라우터에서 설정한 TCP 포트(기본 9443)를 서버에 연결합니다.
5. 클라이언트 서버 주소를 공인 IP/도메인으로 바꾸고 TLS를 켭니다. 사설 CA를 쓰면 클라이언트 CA 파일도 설정합니다.

공인/내부망 인터페이스 바인딩은 TLS가 필수입니다. 비암호화 수신은 루프백 시험만 허용합니다. 설정 예시는 `server.example.json`이며 토큰 자리표시자를 실제 값으로 교체해야 합니다. 인증서 경로와 DB 경로는 설정 파일 디렉터리 기준입니다. `--config`는 하위 명령 **앞**에 지정합니다: `python server.py --config /opt/batterywatch/server.local.json run`.

## 여러 클라이언트

server.local.json의 collectors에 수집기별 고유 id, token_sha256, devices를 추가합니다. 각 수집기는 별도 무작위 토큰을 사용합니다. 토큰은 SHA256 해시로만 서버 설정에 보관하고 원문은 클라이언트 설정에 입력합니다. devices는 허용된 site_id/device_id 쌍 목록입니다. 설정 변경은 서버 재시작 후 적용됩니다. 다른 수집기가 같은 현장/장비로 전송하도록 허용하면 최신 snapshot은 두 수집기 중 captured_at이 최신인 메시지가 됩니다.

토큰 생성 예시 (출력 원문은 안전하게 전달):

```powershell
python -c "import secrets,hashlib; t=secrets.token_urlsafe(32); print('token:',t); print('token_sha256:',hashlib.sha256(t.encode()).hexdigest())"
```

로컬 설정·토큰·인증서·DB는 Git에서 제외합니다. 수집기 ID는 재전송 중복 제거의 기준이므로 운영 중 임의로 바꾸지 마세요.

## 저장 규칙과 범위

- snapshot과 trap 전체 JSON을 보존합니다. SOC, 온도, 셀 데이터, 활성 알람 등 원본 필드를 생략하지 않습니다.
- `samples`에 인증된 collector_id + sample_id를 고유 키로 저장합니다. 동일 데이터 재전송은 중복 저장하지 않고 성공 ACK를 반환합니다.
- 같은 키로 다른 데이터를 보내면 거부합니다. 실패 시 연결을 종료하고 성공 ACK는 보내지 않습니다.
- `devices`에는 가장 최신 captured_at의 snapshot 참조를 유지합니다. 늦게 도착한 과거 데이터는 이력에만 추가하고 최신 상태를 덮어쓰지 않습니다.
- captured_at은 snapshot 생성 시각입니다. 실제 측정의 신선도는 data.last_poll_at, connected, last_poll_ok를 함께 확인해야 합니다.
- 미래 5분 초과 시각, 시간대 없는 시각, 잘못된 스키마/JSON/비유한 숫자, 권한 밖 장비는 거부합니다.
- DB 트랜잭션 커밋 후에만 ACK합니다. 디스크 오류·잠금 등 실패 시 ACK하지 않아 클라이언트가 재전송합니다.
- 기본 동시 연결 32개, 최대 프레임 16 MiB, 미인증 헤더 대기 10초, 본문 대기 15초입니다. 인증된 연결의 유휴 제한 3700초는 클라이언트 최대 업로드 주기 3600초를 수용합니다.
- 저장 데이터 자동 삭제는 하지 않습니다. 디스크 용량과 백업을 관리해야 합니다. 대규모 장비 수에 대한 성능 검증은 아직 하지 않았습니다.
- SQLite DB 하나당 서버 프로세스 하나만 실행합니다. DB는 서버 로컬 디스크에 둡니다.
- 서버 자체 GUI/웹 화면과 운영체제 서비스 자동 등록은 없습니다. Android 화면, 서버 알람, FCM 연동은 구현되어 있습니다.

## 테스트

```powershell
python -m unittest discover -s tests -v
```

서버 시험은 인증/현장 권한, 데이터/Trap 보존, 중복/과거 순서, 저장 실패 ACK 금지, 프레임 오류, 백업, 기존 UploadWorker와의 TCP/TLS 연동을 검증합니다. TLS 시험의 임시 인증서 생성에만 OpenSSL을 사용하며, 없으면 해당 시험은 건너뜁니다. 실제 공인 서버 배포/인증서 연결은 별도로 확인해야 합니다.

## Android API와 알람 활성화

```powershell
python server.py enable-api --site site-01 --device battery-01
python server.py check
python server.py run
```

`android-connection.local.json`에 조회용 토큰이 생성됩니다. 수집기 토큰과 별개이며 기본 API 주소는 `127.0.0.1:8443`입니다. 외부 바인딩 시 TLS 인증서가 필요합니다. 계정별 장비 권한은 `api.viewers[].devices`에서 설정합니다.
운영 수치 임계값은 기본 비활성이며 통신 중단과 장비 자체 알람은 기본 감시합니다. 실제 구현된 경로, 임계값, FCM 설정은 [알람·푸시 안내](../docs/alarms-and-push.md)를 따릅니다.

## 이번에 구현한 항목

- 서버 기준 알람 발생/유지/복구 판정
- 수집 중단 감지: 업로드 요청과 별개로 주기적으로 실행
- Android 조회 API와 사용자별 현장 접근 권한
- 알람 이벤트 영구 저장, FCM 발송 큐와 재시도
- 알림 수신 기기 등록·해제 및 잘못된 토큰 정리


## 통신 디버그 로그

`python3.12 server.py run --debug`로 실행하면 터미널과 설정 파일 옆 `logs/server.log`에 통신 메타데이터를 기록합니다. 일반 실행은 기존 INFO 수준을 유지합니다.

- `API`: 연결/종료, TLS 여부, 요청 메서드·경로 유형, 조회 계정, HTTP 응답 코드, 응답 크기와 처리 시간. 401은 조회 인증 실패, 403은 권한 부족입니다.
- `UPLOAD`: 연결, 프레임 크기, 인증 성공, 저장 후 ACK, 현장·장비·샘플 ID, 중복 여부, 연결 종료/시간 초과 원인. 기존 Rejected 로그도 확인하세요.
- 토큰, Authorization 헤더, 쿼리 문자열, 요청/응답 본문, 개인키와 예외 원문은 기록하지 않습니다. 로그에는 IP와 장비 식별자가 포함됩니다.
- API는 응답 후 연결을 닫으므로 조회할 때마다 연결/종료가 기록되는 것이 정상입니다.
- TLS 핸드셰이크 완료 후의 통신을 기록합니다. 방화벽 차단이나 TLS 핸드셰이크 실패로 애플리케이션에 도달하지 않은 연결은 이 로그에 나타나지 않을 수 있습니다.
- Linux에서 `tail -f logs/server.log`로 확인할 수 있습니다. 디버그를 끄려면 `--debug` 없이 재시작하세요.

## 스마트폰용 모듈 10개 테스트

`python3.12 server.py run --debug --demo-data`로 실행합니다. 기존 서버는 먼저 종료하세요. 기존 HTTPS 주소와 조회 토큰으로 접속하면 `DEMO 배터리 모듈 10개 (가상 데이터)` 장비가 나타납니다. 모듈마다 SOC/SOH, 전압/전류, 셀 15개의 전압/온도가 5초마다 갱신됩니다.

테스트 데이터는 기존 DB 옆 `smartphone-demo.sqlite3`에 저장되고 실측 DB는 수정하지 않습니다. 설정 파일도 변경하지 않습니다. 이 모드에서는 모든 기존 조회 계정이 DEMO 장비만 조회하며 실제 수집기 업로드는 거부하고 푸시를 발송하지 않습니다. APK 변경은 필요 없습니다. 이 모드는 서버-앱 조회 시험이며 실제 TCP 수집기 업로드 시험은 아닙니다.

테스트를 종료하려면 Ctrl+C 후 `python3.12 server.py run --debug`로 재시작하세요. 기존 DB와 권한이 복원됩니다. 테스트 DB의 이력은 남으며 테스트 모드 재실행 시 계속 추가됩니다.

## 이력 보관 정책

일반/데모 서버 모두 시작 직후와 매시간 정리를 실행합니다. 서버 수신 시각 기준 10일을 넘긴 snapshot/trap 이력과 종료된 접속 세션을 오래된 순서로 500건씩 삭제합니다. 장비별 마지막 snapshot과 진행 중인 접속 세션은 보존합니다. 따라서 장기 미접속 장비의 마지막 상태는 10일 이후에도 조회됩니다. 재전송으로 다시 수신한 데이터는 새 수신 시각부터 보관하며, 삭제된 샘플 ID의 중복 여부는 더 이상 확인할 수 없습니다.

`server.local.json`에 다음 항목을 추가하면 정책을 조정할 수 있습니다. 생략해도 이 기본값이 적용됩니다.

```json
"retention": {
  "days": 10,
  "alarm_days": 0,
  "interval_seconds": 3600,
  "batch_size": 500
}
```

`alarm_days: 0`은 알람 이력 무기한 보존입니다. 양수로 설정하면 해당 일수보다 오래된 알람과 연결된 확인/발송완료 기록을 정리하되, 현재 알람 상태가 참조하거나 발송 대기 중인 이벤트는 남깁니다. 이력 삭제는 되돌릴 수 없으므로 기존 자료가 필요하면 업데이트 실행 전에 `python3.12 server.py backup backups/before-retention.sqlite3`으로 백업하세요.

SQLite는 삭제된 공간을 이후 쓰기에 재사용합니다. 파일 크기가 즉시 줄어들지는 않으며 보관 일수는 고정 용량 제한이 아닙니다. 자동 VACUUM은 실행하지 않습니다. `Retention removed` 로그에서 삭제 건수를 확인할 수 있습니다. APK 업데이트는 필요 없습니다.
