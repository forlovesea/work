# Ubuntu 20.04 공인 중계서버

스마트폰 두 대가 각각 LTE/Wi-Fi에서 이 서버로 접속합니다. Python 3.8 이상 표준 라이브러리만 사용하며 pip 패키지나 데이터베이스는 필요하지 않습니다. 중계서버의 TLS 바깥에 별도의 스마트폰 간 TLS가 유지되므로 화면/제어 페이로드는 서버에 평문으로 전달되지 않습니다.

## 준비

- Ubuntu 20.04 서버와 공인 IP, 관리자 권한.
- 공인 IP를 가리키는 도메인(예: `relay.example.com`)과 해당 도메인에 유효한 공인 CA TLS 인증서. IP 직접 입력도 인증서에 그 IP의 SAN이 있고 Android에서 신뢰하는 인증서이면 가능합니다.
- TCP `55000~60000` 중 선택한 포트의 인바운드 허용. 기본 포트는 `55000`입니다. 변경 시 서비스 파일의 `--port`와 Target 앱의 주소를 동일하게 설정하세요. 범위 밖 포트는 서버와 앱 모두 거부합니다. HTTP 서비스가 아닌 TLS 바이트 중계이므로 일반 HTTP reverse proxy에 그대로 연결하지 않습니다.
- 서버 OS 보안 업데이트를 적용하세요. Ubuntu 20.04 환경 자체의 유지보수는 서버 운영자가 관리합니다.

## 설치

### 기존 서버를 v0.4.0으로 업데이트

자동 Target 목록은 **서버와 두 앱 모두 v0.4.0**이 필요합니다. 이 폴더의 `relay.py`와 `update-server.sh`를 Ubuntu 서버의 같은 작업 폴더에 복사한 뒤 실행하세요.

```bash
sudo sh update-server.sh
sudo cat /etc/remotecontrol/access.key
```

업데이트 스크립트는 기존 인증서와 서비스의 포트 설정을 유지하고, 기존 relay.py를 백업한 뒤 새 파일을 설치하고 서비스를 재시작합니다. 진행 중인 연결은 종료됩니다. `/etc/remotecontrol/access.key`가 없으면 256비트 무작위 서버 접속 키를 생성합니다. 기존 키는 보존합니다. 표시한 키를 허용한 Host·Target의 **서버 접속 키** 입력란에 최초 한 번 설정하세요. 키를 알고 있는 앱은 같은 서버의 모든 Target에 대해 목록 조회/공유 승인 후 연결 권한을 갖습니다.

스크립트 실행은 기존 설치가 끝나 있고 `remotecontrol` 그룹과 서비스가 존재하는 서버를 전제로 합니다. 새 설치에는 아래 절차를 사용하세요.

다음은 서버에서 실행할 예시입니다. `relay.py`와 `remotecontrol-relay.service`를 서버의 작업 폴더로 먼저 복사하세요. 도메인/인증서 경로는 실제 값으로 바꿉니다.

```bash
sudo apt-get update
sudo apt-get install -y python3
sudo useradd --system --no-create-home --shell /usr/sbin/nologin remotecontrol
sudo install -d -o root -g root -m 755 /opt/remotecontrol
sudo install -m 644 relay.py /opt/remotecontrol/relay.py
sudo install -d -o root -g remotecontrol -m 750 /etc/remotecontrol
sudo install -o root -g remotecontrol -m 640 /path/to/fullchain.pem /etc/remotecontrol/fullchain.pem
sudo install -o root -g remotecontrol -m 640 /path/to/privkey.pem /etc/remotecontrol/privkey.pem
sudo sh -c 'umask 077; test -f /etc/remotecontrol/access.key || python3 -c "import secrets; print(secrets.token_hex(32))" > /etc/remotecontrol/access.key'
sudo chown root:remotecontrol /etc/remotecontrol/access.key
sudo chmod 640 /etc/remotecontrol/access.key
sudo install -m 644 remotecontrol-relay.service /etc/systemd/system/remotecontrol-relay.service
sudo systemctl daemon-reload
sudo systemctl enable --now remotecontrol-relay
sudo systemctl status remotecontrol-relay
```

서버 방화벽과 클라우드 보안 그룹에서 선택한 TCP 포트 하나를 허용합니다. UFW를 이미 사용 중이라면 기본 설정에서 `sudo ufw allow 55000/tcp`로 추가할 수 있습니다. `55000~60000` 전체 범위를 개방할 필요는 없습니다. 이 프로젝트는 방화벽 전체 설정이나 SSH 접근 설정을 변경하지 않습니다. 높은 포트를 사용하므로 서비스에 특권 포트 바인딩 권한을 부여하지 않습니다.

인증서는 자체 서명 인증서 검증을 끄는 방식으로 우회하지 않습니다. 운영 인증서를 갱신한 뒤 `/etc/remotecontrol/`에 새 인증서를 같은 소유권/권한으로 복사하고 `sudo systemctl restart remotecontrol-relay`를 실행하세요. 재시작하면 진행 중인 세션이 종료됩니다.

Host와 Target에 같은 서버 주소(예: `61.105.141.21:55000`)와 서버 접속 키를 입력합니다. Target에서 서버 연결을 시작하면 Host 목록에 표시되고, Target 화면 공유를 승인하면 연결 가능합니다. 포트를 변경하면 서비스의 `--port`, 방화벽, 두 앱의 주소를 함께 변경하세요.

## 테스트 / 운영

```bash
python3 -m unittest -v test_relay
sudo journalctl -u remotecontrol-relay -f
```

자동 테스트는 루프백에서 중계 프로토콜/데이터 전달을 검증합니다. 실제 인증서 체인, Ubuntu systemd 실행, LTE 기기 연결 검증을 대신하지 않습니다. 실제 기기 항목은 `../docs/DEVICE_TESTS.md`를 확인하세요.

서버는 인증서/개인키와 서버 접속 키 파일 없이 기동하지 않습니다. 키 파일 기본 경로는 `/etc/remotecontrol/access.key`이며 `--access-key-file`로 변경할 수 있습니다. `relay.py --help`에서 실행 옵션을 확인하세요.

## 프로토콜과 제한

첫 줄은 TLS 안의 JSON이며 모든 작업에 `key` 인증이 필요합니다.

1. `PRESENCE`: Target의 안정적인 `id`와 `name`을 등록합니다. Target은 10초마다 `PING`을 보내고 서버는 `PONG`을 반환합니다. 30초 동안 응답이 없거나 소켓 종료 시 등록을 제거합니다.
2. `LIST`: 접속 중인 기기의 `id`, `name`, `state`만 반환합니다. 상태는 `waiting`, `ready`, `busy`입니다. 세션 키는 목록에 포함하지 않습니다.
3. `SHARE`: 사용자가 화면 공유를 승인한 Target이 `id`, `fingerprint`, `token`을 등록합니다.
4. `CONNECT`: 인증된 Host가 기기 `id`로 요청하면 한 Host에만 세션 정보를 제공하고 양쪽에 `PAIRED`를 전송합니다. 이후 내부 TLS 바이트를 양방향 전달합니다.
5. 한쪽 종료 시 공유 소켓을 정리합니다. Target은 공유 권한이 유지되는 동안 새 세션으로 자동 재등록합니다. Host는 목록에서 다시 선택합니다.

기존 인증 없는 `TARGET/HOST` 프로토콜은 운영 모드에서 거부합니다. 단위 테스트용 `Relay(access_key=None)`에서만 기존 프로토콜을 허용합니다.

기본 제한은 동시 소켓 256개, 공유 소켓 대기 5분, 원격 연결 30분, 헤더 대기 10초, 느린 수신 측 쓰기 대기 30초입니다. Target은 등록 유지용 소켓 1개와 공유 소켓 1개를 사용하고 Host 원격 연결 및 목록 조회는 별도 소켓을 사용합니다. 기기 목록과 세션 키는 메모리에만 보관하며 서버 재시작 시 초기화됩니다. Target이 재접속하면 목록이 복구됩니다.

서버가 지문과 세션 키를 전달하므로 서버와 관리자를 신뢰하는 구조입니다. 공통 키를 아는 앱은 서로 신뢰하는 한 그룹으로 취급합니다. 계정별 권한, 사용자별 트래픽 정책, 강력한 DDoS 방어는 구현하지 않았습니다. 기존 APK는 새 서버와 호환되지 않으므로 두 앱도 함께 업데이트하세요.

참고: [Python asyncio streams](https://docs.python.org/3/library/asyncio-stream.html).

## v0.4.4 화면 깨우기 업데이트

Host의 화면 깨우기는 이 버전의 `relay.py`가 필요합니다. 서버에 GitHub 저장소를 받아 둔 경우 저장소 루트에서 다음 명령으로 업데이트하세요.

```sh
git pull --ff-only origin main
cd RemoteControl/server
sudo sh update-server.sh
```

저장소가 없다면 먼저 `git clone https://github.com/forlovesea/work.git`으로 받은 뒤 `work/RemoteControl/server`로 이동하세요. `update-server.sh`는 기존 서비스가 설치된 서버용입니다. 최초 설치는 위 설치 절차를 따르세요. 기존 인증서, 접속 키, 서비스 인수를 유지합니다. Host와 Target도 v0.4.4로 업데이트하세요.

인증된 WAKE 요청은 해당 Target의 다음 PING 응답에 요청 ID와 함께 전달됩니다. Target의 화면 상태 응답을 최대 12초 기다리고, 중복 요청은 거부하며 미전달 만료 요청은 폐기합니다. 기존 Target에는 WAKE를 전달하지 않습니다. 서버가 받는 awake는 Target이 보고한 화면 활성 상태이며 잠금 해제나 화면 공유의 성공을 의미하지 않습니다.
