# Ubuntu 서버에서 내려받아 실행

저장소: https://github.com/forlovesea/work

프로젝트 경로: `WebConference/RelayServer` (이전 한글 서버 폴더 이름 대신 사용).

## 준비

64비트 Linux, Git, Python 3(모델 다운로드용), Docker Engine 및 Compose 플러그인이 필요합니다. 앱은 컨테이너의 Python 3.12를 사용하므로 Ubuntu 20.04 기본 Python에 requirements를 설치하지 마세요.

Ubuntu 20.04에서 이미 동작하는 Docker와 Compose를 사용하는 배포 구성입니다. 2026-10-15 확인 기준 [Docker의 현재 Ubuntu 지원 목록](https://docs.docker.com/engine/install/ubuntu/)에는 20.04가 없습니다. 새 설치라면 지원되는 Ubuntu LTS를 권장하며, 20.04 유지 시 해당 OS와 호환되는 Docker 설치를 먼저 준비해야 합니다. 이 프로젝트의 실제 Ubuntu 20.04 실행은 아직 검증하지 않았습니다.

```bash
sudo apt update
sudo apt install -y git python3 ca-certificates
sudo docker version
sudo docker compose version
```

## 다운로드와 설정

```bash
git clone https://github.com/forlovesea/work.git
cd work/WebConference/RelayServer
cp .env.example .env
nano .env
```

`.env`의 `DOMAIN=meet.example.com`을 실제 도메인으로 바꾸세요. 해당 도메인의 DNS가 서버를 가리켜야 합니다. DB_PATH와 VOSK_MODEL_PATH는 컨테이너 경로인 기본값을 유지합니다. 비공개 저장소인 경우 clone 시 GitHub 인증이 필요합니다.

```bash
python3 scripts/download_model.py
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 meeting https
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/config
```

`ok: true` 및 `speech_available: true`를 확인하고 `https://설정한도메인`에 접속하세요. 자동 회의록이 필요 없다면 모델 다운로드를 생략할 수 있습니다.

## 네트워크

- HTTPS 발급/접속용 TCP 80, 443이 서버에 도달해야 합니다.
- WebRTC는 HTTPS와 별도 UDP 연결이 필요합니다. `cat /proc/sys/net/ipv4/ip_local_port_range`로 서버 범위를 확인하고 방화벽 및 공유기 설정에 반영하세요.
- 외부망/NAT 환경은 [RelayServer README](RelayServer/README.md)의 TURN 설정을 적용하세요. `deploy/turnserver.conf`의 도메인·비밀번호·공인 IP와 `.env`의 `ICE_SERVERS_JSON`을 일치시키고 TCP/UDP 3478, UDP 49160–49260 접근을 구성한 다음 `sudo docker compose --profile turn up -d --build`로 시작합니다.
- 다른 PC의 카메라·마이크 사용에는 HTTPS가 필요합니다. `localhost` 주소는 해당 PC 자체를 가리킵니다.

## 업데이트와 종료

```bash
# RelayServer 디렉터리에서 실행
git pull --ff-only
sudo docker compose up -d --build
# 종료 (회의록 볼륨 보존)
sudo docker compose down
```

회의록은 `meeting-data` Docker 볼륨에 저장됩니다. `down -v`는 데이터를 삭제하므로 사용하지 마세요. 업데이트 전에 진행 중인 회의를 종료하고 운영 DB를 백업하세요. 재부팅 시 Docker 서비스가 시작되면 `restart: unless-stopped` 설정으로 컨테이너가 다시 시작됩니다.

Windows의 `.venv`, 기존 회의록 DB, 모델 파일, `.env`는 GitHub 업로드에서 제외되어 있습니다. 기존 회의록 이전은 별도 백업/복원이 필요합니다.
