# Ubuntu 20.04 직접 설치·운영

문서 업데이트: **2026년 10월 19일 · 기능 기준 2392a2d**. 일반 사용자의 새 회의 생성은 Master 이메일 승인 후 가능하며, Master 비밀번호 인증 사용자는 승인 없이 직접 생성합니다. 설치·업데이트 전에 [이메일 및 SMTP 설정](MASTER_APPROVAL.md)과 [Master 키 등록](MASTER_ADMIN.md)을 확인하세요.

**현재 운영 주소는 `https://61.105.141.21:10443`입니다.** 축전지·원격제어 서비스가 함께 운영되는 기존 서버는 [서버 운영 안내](SERVER_OPERATIONS.md)를 우선하고 Nginx·인증서·방화벽을 일괄 변경하지 않습니다. 공인 IP·10443 신규 설치 순서는 [통합 매뉴얼 10장](화상회의_상세매뉴얼.html#section-10)에 있습니다. 아래 2장의 도메인·80/443 예시는 해당 방식을 새로 선택할 때만 사용합니다.

한국어 회의록의 정확도를 우선하고 지연을 허용하려면 [Whisper 전환 안내](WHISPER_DEPLOY.md)를 참고하세요. 기존 설치의 음성 인식 엔진만 교체하는 절차를 제공합니다.

구성: **Nginx(HTTPS/WebSocket) → Python 3.12 + aiortc(systemd)**. 외부망 NAT 중계가 필요하면 Ubuntu 패키지 coturn을 추가합니다. 설치 대상은 Ubuntu 20.04 x86_64입니다.

Ubuntu 기본 Python 3.8은 OS용으로 유지합니다. 공식 CPython 3.12.15 소스를 SHA-256 검증 후 `/opt/moa/python/3.12.15`에 별도 설치합니다. [Python 릴리스](https://www.python.org/downloads/release/python-31215/). Ubuntu 20.04는 표준 지원이 종료되었으므로 OS 보안 업데이트는 Ubuntu Pro/ESM 등으로 관리해야 합니다. [Ubuntu 지원 안내](https://ubuntu.com/blog/ubuntu-20-04-lts-end-of-life-standard-support-is-coming-to-an-end-heres-how-to-prepare).

## 1. 다운로드 및 최초 설치

```bash
sudo apt update
sudo apt install -y git ca-certificates
git clone https://github.com/forlovesea/work.git
cd work/WebConference/RelayServer
sudo bash deploy/native/build-python.sh
sudo bash deploy/native/install.sh
```

빌드는 기본 2개 작업으로 실행합니다. 메모리가 부족하면 `sudo env JOBS=1 bash deploy/native/build-python.sh`를 사용하세요. 기존 별도 Python 3.12가 있다면 빌드를 생략하고 `sudo bash deploy/native/install.sh /절대경로/python3.12`로 설치할 수 있습니다. 서비스는 홈 디렉터리에 접근하지 못하므로 Python을 `/home` 아래에 설치하지 마세요.

설치기는 전용 `moa` 계정, 릴리스별 가상환경, 한국어 모델, 설정 파일, systemd 서비스를 구성합니다. 설정은 최초 한 번만 생성하며 업데이트 때 보존합니다. 서버는 `127.0.0.1:8000`에서만 HTTP 요청을 받습니다. 설치 직후 외부 HTTPS는 아직 구성되지 않은 상태입니다.

| 위치 | 용도 |
| --- | --- |
| `/opt/moa/releases/release-*` | 버전별 코드와 가상환경 |
| `/opt/moa/current` | 현재 버전 심볼릭 링크 |
| `/etc/moa/moa.env` | 환경 설정, root:moa 0640 |
| `/etc/moa/master-key.json` | Master 키 해시, root:moa 0640, Git에 포함하지 않음 |
| `/var/lib/moa/meetings.db` | 회의록 DB |
| `/var/lib/moa/models` | 한국어 모델 |
| `/etc/systemd/system/moa.service` | 전용 계정 서비스 |

```bash
sudo systemctl status moa --no-pager
sudo journalctl -u moa -n 100 --no-pager
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/config
```

`ok: true`, `speech_available: true`를 확인하세요. 기본 `MAX_PARTICIPANTS=8`은 접속 제한이며 동시 성능 보장값이 아닙니다. 실제 참석 인원으로 CPU·메모리·네트워크 부하를 시험하세요.

### Master 키 최초 등록

```bash
sudo /opt/moa/current/.venv/bin/python /opt/moa/current/scripts/set_master_key.py
```

사용할 키를 두 번 입력합니다. 입력 문자는 표시되지 않습니다. 키 분실 시에도 같은 명령으로 새 키를 지정하며 키만 변경할 때는 재시작하지 않습니다. 환경 파일에 PUBLIC_BASE_URL과 필요 시 SMTP·Whisper 설정을 추가한 경우에는 회의가 없는 시간에 Moa를 재시작합니다. 실제 비밀번호를 코드나 문서에 넣지 않습니다.

## 2. HTTPS 설정 — 도메인 기반 신규 구성 예시

DNS가 실제 서버를 가리키고 TCP 80/443이 도달 가능해야 합니다. 기존 프록시가 있다면 포트를 중복 점유하지 않도록 기존 설정에 사이트를 추가하세요.

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo cp deploy/native/nginx.conf /etc/nginx/sites-available/moa
sudo nano /etc/nginx/sites-available/moa
# server_name을 실제 도메인으로 변경
sudo ln -s /etc/nginx/sites-available/moa /etc/nginx/sites-enabled/moa
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
# 아래 도메인도 실제 값으로 변경
sudo certbot --nginx -d meet.example.com --redirect
sudo systemctl enable --now certbot.timer
sudo certbot renew --dry-run
```

`https://실제도메인`으로 접속하세요. Nginx는 WebSocket Upgrade 전달과 긴 연결을 지원하도록 구성했습니다. [공식 설명](https://nginx.org/en/docs/http/websocket.html). 폐쇄망은 조직 CA 인증서를 Nginx에 설정하고 클라이언트가 해당 CA를 신뢰하도록 구성하세요. 다른 PC의 카메라·마이크·화면 공유에는 신뢰되는 HTTPS가 필요합니다.

## 3. 미디어 및 TURN

WebRTC 미디어는 HTTPS와 별도 UDP 연결입니다. `cat /proc/sys/net/ipv4/ip_local_port_range`로 서버 범위를 확인하고 방화벽·보안그룹·NAT에 반영하세요. NAT 환경은 TURN을 구성하고 서로 다른 외부 네트워크에서 시험해야 합니다. HTTP 8000은 외부에 열지 않습니다.

```bash
sudo apt install -y coturn
# 기존 coturn 운영 중이면 덮어쓰지 말고 기존 설정에 통합
sudo cp deploy/turnserver.conf /etc/turnserver.conf
sudo nano /etc/turnserver.conf
```

`realm`, `user=meeting:강한임의비밀번호`, 필요 시 `external-ip=공인IP/사설IP`를 설정합니다. TCP/UDP 3478과 UDP 49160–49260을 허용합니다. `/etc/default/coturn`을 사용하는 패키지는 `TURNSERVER_ENABLED=1`도 설정합니다.

```bash
sudo systemctl enable --now coturn
sudo systemctl restart coturn
sudo journalctl -u coturn -n 50 --no-pager
sudo nano /etc/moa/moa.env
```

systemd 환경 파일에서는 JSON 전체를 작은따옴표로 감쌉니다.

```text
ICE_SERVERS_JSON='[{"urls":"turn:meet.example.com:3478?transport=udp","username":"meeting","credential":"실제비밀번호"}]'
```

`sudo systemctl restart moa`로 적용합니다. 재시작은 진행 중인 회의를 종료합니다. worker 수를 늘리면 방과 WebRTC 상태를 공유하지 못하므로 단일 프로세스를 유지하세요.

## 4. 업데이트와 롤백

최신 통신 상태·웹캠 화질 기능은 별도 패키지나 환경 변수 추가 없이 앱 업데이트로 적용됩니다. `static/media-quality.js`도 배포되어야 하므로 app.js만 단독 복사하지 않습니다. 적용 후 브라우저에서 Ctrl+F5로 새로고침합니다. 화질은 기본 자동이며 기존 서버에 1080p를 일괄 강제하지 않습니다.

회의를 종료하고 백업한 뒤 Git 체크아웃의 `RelayServer`에서:

```bash
git pull --ff-only
sudo bash deploy/native/install.sh
```

새 릴리스에서 의존성과 모델을 확인한 뒤 `current` 링크를 전환하고 서비스를 재시작합니다. 기존 가상환경·DB·설정은 덮어쓰지 않습니다. 이전 릴리스 경로를 출력하며 자동 삭제하지 않습니다. 시작 후 상태 검사가 실패하면 종료 코드 1로 중단합니다. 필요하면 수동 롤백하세요.

```bash
sudo systemctl stop moa
# 실제 이전 릴리스 경로로 변경
sudo ln -sfn /opt/moa/releases/release-PREVIOUS /opt/moa/current
sudo systemctl start moa
```

롤백은 코드·가상환경만 바꾸며 DB 및 설정은 되돌리지 않습니다. 향후 DB 형식 변경은 해당 버전 복원 지침도 확인해야 합니다. Python 보안 패치는 별도 설치 후 새 인터프리터를 `install.sh` 인자로 전달하여 가상환경을 다시 만드세요.

## 5. 자동 시작, 로그, 백업

```bash
sudo systemctl is-enabled moa
sudo systemctl restart moa
sudo systemctl stop moa              # 이번 실행만 중지
sudo systemctl disable --now moa     # 부팅 자동 시작 해제
sudo systemctl enable --now moa      # 재개
sudo journalctl -u moa -f
```

설치기가 부팅 자동 시작을 등록합니다. 재부팅 후 서비스가 살아나도 진행 중이던 방은 복구되지 않으므로 새 방을 만드세요.

회의 종료 후 서비스를 멈추고 DB와 WAL/SHM을 포함한 상태 디렉터리 및 설정을 함께 백업합니다. 백업에는 회의록과 TURN 암호가 포함됩니다.

```bash
sudo systemctl stop moa
sudo install -d -m 0700 /var/backups/moa
sudo sh -c 'umask 077; tar -czf /var/backups/moa/backup-$(date +%Y%m%d-%H%M%S).tar.gz /var/lib/moa /etc/moa'
sudo systemctl start moa
```

복원은 서비스를 멈춘 상태에서 수행하고 `/var/lib/moa` 소유자를 `moa:moa`로 유지하세요. 기존 서버의 DB 이전도 양쪽 서비스를 중지하고 남아 있는 WAL/SHM까지 함께 옮깁니다. 새 DB와 기존 DB를 각각 백업한 뒤 이전하세요.

## 검증 범위

Windows에서 앱 회귀 테스트와 설치 셸 구문 검사를 수행합니다. Ubuntu의 apt 설치·소스 컴파일·systemd/Nginx/coturn 실행과 외부망 연결은 대상 서버에서 최종 검증해야 합니다.
