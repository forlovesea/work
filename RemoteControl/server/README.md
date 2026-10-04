# Ubuntu 20.04 공인 중계서버

스마트폰 두 대가 각각 LTE/Wi-Fi에서 이 서버로 접속합니다. Python 3.8 이상 표준 라이브러리만 사용하며 pip 패키지나 데이터베이스는 필요하지 않습니다. 중계서버의 TLS 바깥에 별도의 스마트폰 간 TLS가 유지되므로 화면/제어 페이로드는 서버에 평문으로 전달되지 않습니다.

## 준비

- Ubuntu 20.04 서버와 공인 IP, 관리자 권한.
- 공인 IP를 가리키는 도메인(예: `relay.example.com`)과 해당 도메인에 유효한 공인 CA TLS 인증서. IP 직접 입력도 인증서에 그 IP의 SAN이 있고 Android에서 신뢰하는 인증서이면 가능합니다.
- TCP `55000~60000` 중 선택한 포트의 인바운드 허용. 기본 포트는 `55000`입니다. 변경 시 서비스 파일의 `--port`와 Target 앱의 주소를 동일하게 설정하세요. 범위 밖 포트는 서버와 앱 모두 거부합니다. HTTP 서비스가 아닌 TLS 바이트 중계이므로 일반 HTTP reverse proxy에 그대로 연결하지 않습니다.
- 서버 OS 보안 업데이트를 적용하세요. Ubuntu 20.04 환경 자체의 유지보수는 서버 운영자가 관리합니다.

## 설치

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
sudo install -m 644 remotecontrol-relay.service /etc/systemd/system/remotecontrol-relay.service
sudo systemctl daemon-reload
sudo systemctl enable --now remotecontrol-relay
sudo systemctl status remotecontrol-relay
```

서버 방화벽과 클라우드 보안 그룹에서 선택한 TCP 포트 하나를 허용합니다. UFW를 이미 사용 중이라면 기본 설정에서 `sudo ufw allow 55000/tcp`로 추가할 수 있습니다. `55000~60000` 전체 범위를 개방할 필요는 없습니다. 이 프로젝트는 방화벽 전체 설정이나 SSH 접근 설정을 변경하지 않습니다. 높은 포트를 사용하므로 서비스에 특권 포트 바인딩 권한을 부여하지 않습니다.

인증서는 자체 서명 인증서 검증을 끄는 방식으로 우회하지 않습니다. 운영 인증서를 갱신한 뒤 `/etc/remotecontrol/`에 새 인증서를 같은 소유권/권한으로 복사하고 `sudo systemctl restart remotecontrol-relay`를 실행하세요. 재시작하면 진행 중인 세션이 종료됩니다.

앱의 Target 화면에서 `relay.example.com:55000`을 입력합니다. Host는 Target에서 전달받은 접속 정보에 포함된 동일 서버와 포트로 연결합니다. 예를 들어 `58000`을 사용하려면 서비스 파일의 `--port 58000`, 방화벽의 `58000/tcp`, Target의 `relay.example.com:58000`을 함께 맞춥니다. 설치된 서비스 파일을 수정했다면 `sudo systemctl daemon-reload` 후 `sudo systemctl restart remotecontrol-relay`를 실행합니다.

## 테스트 / 운영

```bash
python3 -m unittest -v test_relay
sudo journalctl -u remotecontrol-relay -f
```

자동 테스트는 루프백에서 중계 프로토콜/데이터 전달을 검증합니다. 실제 인증서 체인, Ubuntu systemd 실행, LTE 기기 연결 검증을 대신하지 않습니다. 실제 기기 항목은 `../docs/DEVICE_TESTS.md`를 확인하세요.

서버는 인증서/개인키 파일 없이 기동하지 않습니다. `relay.py --help`에서 실행 옵션을 확인할 수 있습니다.

## 프로토콜과 제한

1. Target이 검증된 TLS 연결로 `TARGET <32자리 방 ID>\n`을 전송하면 서버는 `READY\n`을 반환합니다.
2. Host가 별도 TLS 연결로 `HOST <동일 방 ID>\n`을 전송합니다.
3. 서버가 양쪽에 `PAIRED\n`을 반환한 이후에는 내부 TLS 바이트를 양방향 전달합니다.
4. 한쪽 종료 시 반대 연결도 종료합니다. 방은 재사용하지 않습니다.

기본 제한은 동시 소켓 256개(연결된 한 세션은 2개), 대기 5분, 연결 30분, 헤더 대기 10초, 느린 수신 측 쓰기 대기 30초입니다. 중계 방 식별자는 로그에 남기지 않으며 파일로 저장하지 않습니다. TLS 서버는 연결 IP와 트래픽 양/시점 및 방 ID는 알 수 있습니다.

프로토타입에는 계정 인증, 사용자별 대역폭/요금 정책, 강력한 DDoS 방어가 없습니다. 공개 운영 규모로 확장할 때는 방 등록 권한, 사용자별 제한, 모니터링을 추가하세요. 시스템 연결 한도는 기본적인 자원 제한이며 완전한 남용 방지책이 아닙니다.

참고: [Python asyncio streams](https://docs.python.org/3/library/asyncio-stream.html).
