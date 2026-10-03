# TBC1000B 기반 모니터링 업로드 클라이언트

`RMS_Server/TBC1000B_감시프로그램_V3.2.6.py`의 독립 복사본 `monitor.py`에 TCP 업로드를 추가했습니다. 원본은 수정하지 않았으며 원본 해시는 `BASE_SOURCE.txt`에 기록했습니다.

## 실행

원본 SNMP 스택 호환을 위해 **Python 3.10**을 사용합니다.

```powershell
cd C:\Users\Administrator\Downloads\proj\GITHUB\work\BatteryWatch\monitoring-client
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe monitor.py
```

`run.bat`은 위에서 만든 `.venv`의 Python으로 실행합니다. 프로필을 선택/생성하고 기존 방식으로 SNMP 장비에 연결합니다. 프로필은 이 프로젝트의 `profiles` 폴더에 별도로 저장합니다. 새 checkout에서는 [환경 재현 안내](../docs/reproduce.md)의 `bootstrap.py client --test`를 사용할 수 있습니다.

## 서버 TCP 업로드 설정

창 하단의 **서버 TCP 업로드 설정** 버튼을 누릅니다.

| 항목 | 동작 |
| --- | --- |
| 업로드 사용 | 기본 꺼짐. 서버 설정 후 활성화 |
| 서버 IP / 호스트 | 주소만 입력, URL 형식 아님 |
| TCP 포트 | 기본 9443, 서버와 일치시킴 |
| 업로드 주기 | 기본 **5초**, 1~3600초, 저장 즉시 적용 |
| TLS | 기본 켜짐. IP 접속은 인증서의 IP SAN 필요 |
| CA 파일 | 사설 CA의 PEM 경로, 비우면 시스템 신뢰 저장소 |
| 토큰 | 서버 발급 수집기 인증 토큰 |
| 현장 ID / 장비 ID | 서버에서 사용하는 고정 식별자 |

설정은 프로필 INI에 저장되어 재실행 시 복원됩니다. 토큰도 해당 파일에 저장되므로 파일 접근 권한을 제한하세요. 프로필과 로컬 DB는 Git에서 제외합니다.

업로드 주기는 현재 수집된 상태의 **전송 주기**이며 기존 SNMP 수집 주기를 바꾸지 않습니다. 수집 실패 시 이전 값과 마지막 성공 수집 시각, 실패 상태를 함께 보냅니다. 화면 하단 ACK는 서버 저장 확인을 뜻하며 장비의 최신 측정을 뜻하지 않습니다.

## 전송 항목

- 전체 수신 SNMP OID/값 (`raw_oids`): 원본에서 수집한 범위 전체
- 모듈 매핑·장비 식별·모듈 통신 상태 코드/상태명(Online, Offline, Sleep 등)·전압·전류·SOC·SOH, 셀 전압·온도
- 활성 알람, 고장 목록, 방전 횟수, 충전 보호 상태, 충전전류제한 및 지원되는 SOC 충전제한, 시스템 요약, 설치 순서, EPO 표시 상태
- 앱의 충전전류제한 변경 요청: 허용된 0.05~1.00 C만 SNMP SET하고 GET으로 확인한 결과를 다음 snapshot에 회신
- 장비 연결 상태, SNMP 실패 횟수, 마지막 성공 시각과 오류
- 수신 Trap 원문·수신 시각: 발생과 복구를 각각 별도 메시지로 저장

Trap은 5초 사이의 발생/복구를 놓치지 않도록 저장 즉시 전송합니다. 업로드가 꺼져 있을 때는 업로드 큐에 기록하지 않습니다. 장비가 제공하지 않았거나 원본이 수집하지 않는 OID를 추가로 읽는 기능은 아닙니다. SNMP community와 UI 객체는 전송하지 않습니다.

Master가 다른 장비로부터 받은 Trap도 `_source_ip`를 보존합니다. 서버는 이를 실제 장비와 매핑해야 합니다. 원본의 로컬 장비 제어 기능은 유지되며, 앱의 충전전류제한 원격 설정 명령도 지원합니다.

## 장애 처리

- 네트워크 통신은 별도 스레드에서 수행합니다.
- SQLite 큐에 저장 후 전송하며 동일 ID의 성공 ACK를 받아야 삭제합니다.
- 실패 시 1, 2, 4, … 최대 60초 간격으로 재접속합니다.
- 재실행 후 같은 프로필/설정이면 대기 데이터를 재전송합니다.
- 서버/토큰/식별자/TLS 설정 변경 시 기존 큐는 보존하고 이전 목적지 데이터는 보내지 않습니다. 기존 설정 복원 시 해당 큐가 전송됩니다.
- 프로필당 큐 데이터 한도는 512 MiB입니다. 초과/디스크 오류 시 기존 데이터는 유지하고 신규 저장 실패 경고를 표시합니다. 이후 일부 데이터는 유실될 수 있습니다.
- 오래된 데이터부터 전송하므로 긴 대기열이 있으면 새 알람도 지연될 수 있습니다.

## 로컬 수신 시험

`test_receiver.py`는 **127.0.0.1 전용 비암호화 TCP 시험 도구**이며 운영 서버가 아닙니다.

```powershell
$env:BATTERYWATCH_TEST_TOKEN = 'local-test-only'
python test_receiver.py --port 9443 --database receiver.sqlite3
```

앱에서 서버 `127.0.0.1`, 포트 `9443`, TLS 해제, 동일 토큰, 현장 ID `test-site`, 장비 ID `test-device`를 설정하고 업로드를 켭니다. 기본 5초 후 DB 저장과 ACK를 확인할 수 있습니다. SNMP 연결 전에는 연결 안 됨 상태가 전송됩니다.

[server 디렉터리](../server/README.md)에 TCP/TLS 수신·저장 서버가 구현되어 있습니다. 해당 서버에서 생성한 클라이언트 연결 값을 입력하면 됩니다. [TCP 수신 규격](../docs/tcp-upload-protocol.md)을 사용하며 HTTP 서버에 바로 연결하는 규격이 아닙니다.

## 자동 시험

```powershell
python -m unittest discover -s tests -v
```

프레임 분할, 큐 영속성/목적지 분리/용량 한도, ACK/중복 제거, 잘못된 ACK, 재접속, 실제 Qt 화면의 설정 저장·주기 변경·snapshot·발생/복구 Trap을 시험합니다. 실제 장비·공인 서버·TLS 인증서 연동은 별도 현장 시험이 필요합니다.
