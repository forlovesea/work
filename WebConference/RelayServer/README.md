# 모아 · Python 화상회의 중계서버

일반 참여자·방장·서버 관리자의 세부 절차는 **[통합 상세 매뉴얼](../화상회의_상세매뉴얼.html)** 또는 [역할별 원문](../매뉴얼/00_매뉴얼_안내.md)을 참고하세요. Ubuntu 20.04의 현재 지원 조건과 부팅 자동 시작 등록은 상세 매뉴얼에 설명되어 있습니다.

Python 중계 서버와 브라우저 클라이언트로 구성한 첫 실행 버전입니다. 서버는 FastAPI + aiortc, 음성 인식은 Vosk 한국어 모델, 기록 저장은 SQLite를 사용합니다. 클라이언트는 설치 없이 Chrome/Edge에서 접속하며 브라우저의 카메라·화면 공유 API를 사용하는 부분은 JavaScript입니다.

이 디렉토리(`화상회의/RelayServer`)가 서버의 독립 실행·배포 단위입니다. 영상·음성은 이 Python 서버를 경유하며, HTTPS(Caddy)와 NAT 중계(coturn)는 `deploy/` 및 Compose로 함께 구성합니다. 방 생성·입장 API, WebRTC 연결 협상, 발표권 제어, 화이트보드 동기화, 음성 인식 및 회의록 저장을 포함합니다.

## 구현 범위

| 기능 | 동작 |
| --- | --- |
| 접속 설정 | 중계 서버 주소, 내 이름, 방 접속 ID, 마이크·스피커·카메라 설정 |
| 장치 기본값 | **마이크·스피커 꺼짐**. 카메라도 꺼짐. 이전 사용 여부를 저장하지 않음 |
| 방 생성 | 방장, 방 이름, FREE Talk/회의 모드 선택, 무작위 접속 ID 자동 생성 |
| 초대 | 방장 화면에서 초대 링크 복사. 링크를 열면 서버 주소·접속 ID 자동 입력 후 이름을 확인하고 입장. 기존 주소·ID 복사도 지원 |
| FREE Talk | 모든 참석자가 동시에 말할 수 있고 수신 브라우저가 여러 음성을 동시에 재생 |
| 회의 모드 | 방장이 발표자 지정. 손들기 지원. 서버에서 발표자 외 음성 차단 |
| 자동 회의록 | 회의 모드에서 선택. 서버의 한국어 음성 인식 → 발언자·시간별 전사 → SQLite 저장 |
| 정리된 회의록 | 발언자별 논의, 방장 확정 결정, 실행 항목, 추가 메모, 자동 추출 후보, 시간순 원문을 Markdown으로 저장 |
| 다중 화면 | 모든 참석자의 영상 타일. 음성은 화면 배치에 관계없이 재생 |
| 발표자 화면 | 발표자 영상 또는 공유 화면을 크게 표시. 전체 화면 버튼 지원 |
| 화이트보드 | 현재 발표자가 그리기·색·두께·지우기 제어. 늦게 들어와도 기존 그림 동기화 |
| 열린 파일 | 화면 공유 버튼에서 파일을 연 창·탭·화면 선택. 파일 업로드나 공동 편집은 아님 |
| 방장 퇴장 | 남은 참석자에게 방장 권한 자동 이전. 마지막 참석자 퇴장 시 방 종료 |

회의 모드는 회의록 옵션이 꺼져 있어도 한 사람씩 발표합니다. 발표권 부여만으로 마이크를 자동으로 켜지 않습니다. 참석자가 직접 마이크를 켜야 합니다. FREE Talk에서도 화면 공유·화이트보드의 발표자는 방장이 지정합니다.

## 현재 Windows PC에서 실행

`화상회의/RelayServer` 디렉토리에서:

현재 PC에는 상위 `화상회의/.venv`에 패키지와 이 디렉토리의 `models/`에 한국어 모델이 준비되어 있으므로 **`.\run.cmd`**로 바로 실행할 수 있습니다. 또는 `..\.venv\Scripts\python.exe server.py`를 실행하세요. 새 PC에서는 아래 최초 설치 절차를 따르세요.

```powershell
# 최초 설치: Python 3.12가 필요합니다.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/download_model.py

# 실행
.\.venv\Scripts\python.exe server.py
```

브라우저에서 **http://localhost:8000**을 엽니다. `run.cmd`로도 실행할 수 있습니다. PowerShell 실행 정책이 허용하는 환경에서는 `run.ps1`도 가능합니다. 이 작업에서 만들어진 `.venv`가 있으면 최초 설치 단계는 생략할 수 있습니다. 모델 다운로드를 생략하면 화상회의·수동 기록은 가능하고 자동 회의록 옵션은 비활성화됩니다.

1. 내 이름을 입력하고 **새 회의 만들기**를 선택합니다.
2. 회의 이름과 방식을 지정합니다. 필요하면 자동 회의록을 켭니다.
3. 방장이 **참석자** 탭의 **초대 링크 복사**로 링크를 공유합니다.
4. 다른 브라우저/PC는 링크를 열고 이름을 확인한 뒤 **회의 참여하기**를 누릅니다. 다른 PC에서는 접속 가능한 HTTPS 주소가 필요하며 localhost 링크는 사용할 수 없습니다.
5. 각자 스피커를 켜야 상대방 음성이 들립니다. 발언자는 마이크를 직접 켭니다.
6. 회의 모드에서는 참석자가 손을 들고 방장이 **발표 지정**을 누릅니다.
7. **회의록** 탭에서 전사를 보고 방장이 확정 결정·실행 항목을 추가합니다.
8. 퇴장 전에 **회의록 저장**을 누릅니다. 서버에는 퇴장 후에도 기록이 보관됩니다.

로컬 2개 탭 시험은 가능하지만 실제 음성 시험에는 헤드셋 또는 서로 다른 장치를 권장합니다. 공유 화면에는 시스템 소리가 포함되지 않으며 발표자의 마이크 음성을 사용합니다.

## Ubuntu 20.04 서버 배포

호스트 OS는 Ubuntu 20.04를 사용할 수 있습니다. 애플리케이션은 Docker의 Python 3.12 / Debian Bookworm 이미지 안에서 실행하므로 Ubuntu 기본 Python 3.8에 최신 미디어 패키지를 직접 설치할 필요가 없습니다. 이 작업 환경에서는 Docker 및 실제 Ubuntu 호스트 검증을 수행하지 않았습니다.

준비물: 서버에 설치된 Docker Engine + Compose v2, 서버를 가리키는 DNS 도메인, 외부에서 접속 가능한 HTTPS/미디어 포트.

```bash
cd 화상회의/RelayServer
cp .env.example .env
# .env에서 DOMAIN을 실제 도메인으로 변경
python3 scripts/download_model.py
docker compose up -d --build
docker compose logs -f meeting
```

`https://설정한도메인`으로 접속합니다. Caddy가 HTTPS와 WebSocket 프록시를 처리합니다. 로컬호스트 외 접속은 카메라·마이크·화면 공유를 위해 HTTPS가 필요합니다. 앱은 127.0.0.1:8000에만 바인딩하며 외부 웹 접속은 Caddy를 통해 받습니다.

네트워크 설정:

- TCP 80/443: Caddy HTTPS 발급 및 웹 접속. 해당 도메인의 DNS가 서버를 가리켜야 합니다.
- WebRTC UDP: 서버의 `cat /proc/sys/net/ipv4/ip_local_port_range` 범위를 확인하고 클라이언트에서 도달 가능하게 허용합니다. 리눅스에서 흔한 범위는 32768–60999이지만 실제 값을 따르세요. 앱은 현재 미디어 UDP 포트 범위를 별도로 고정하지 않습니다.
- 방화벽·클라우드 보안 그룹·NAT가 있으면 HTTPS 연결만 성공하고 영상은 실패할 수 있습니다. 이런 환경에서는 TURN 설정이 필요합니다.
- Compose의 `network_mode: host`는 Linux 호스트용입니다. Windows 개발은 위의 직접 실행 절차를 사용하세요.

### 인터넷 / NAT 환경의 TURN

1. `deploy/turnserver.conf`에서 `realm`, 강한 임의 비밀번호, 필요시 `external-ip=공인IP/사설IP`를 설정합니다.
2. `.env`의 `ICE_SERVERS_JSON`을 예시에 맞춰 STUN/TURN 주소 및 동일한 계정으로 설정합니다.
3. TCP/UDP 3478과 UDP 49160–49260을 열고 NAT 환경에서는 해당 포트를 전달합니다.
4. `docker compose --profile turn up -d --build`로 실행합니다.

TURN의 예제 계정은 반드시 변경하세요. 현재는 방 참석자에게 고정 TURN 자격 증명을 전달하는 소규모 초기 구성입니다. 공개 서비스로 확장할 때는 임시 TURN 자격 증명, 계정 인증, 요청 제한 및 운영 모니터링을 추가해야 합니다. 서로 다른 외부 네트워크에서 영상·음성 실접속 시험도 필요합니다.

### 환경 변수

| 이름 | 기본값/설명 |
| --- | --- |
| `DOMAIN` | Compose HTTPS 도메인 |
| `DB_PATH` | 로컬 `data/meetings.db`, Compose `/app/data/meetings.db` |
| `VOSK_MODEL_PATH` | `models/vosk-model-small-ko-0.22`의 절대 경로 |
| `MAX_PARTICIPANTS` | 8, 초기 인원 제한이며 8명 부하 성능을 보증하는 값은 아님 |
| `MAX_ROOMS` | 30 |
| `ICE_SERVERS_JSON` | `[]`, 브라우저와 Python WebRTC 서버에서 함께 사용 |
| `ALLOWED_ORIGINS` | 별도 주소에서 접속 설정 화면을 제공할 때 허용할 origin 목록(쉼표 구분) |

로컬 실행에서 `.env`를 사용하려면 `python server.py --env-file .env` 또는 `.\run.ps1 -EnvFile .env`로 실행하세요. `.env.example`의 `/app/...` 경로는 Docker용이므로 Windows에서는 로컬 절대 경로로 바꾸거나 해당 변수를 생략해야 합니다. 서버는 단일 worker로 실행합니다. 방·미디어 연결은 프로세스 메모리에 있습니다.

Python 3.12와 패키지를 직접 설치한 Linux에서는 `bash run.sh`로 실행할 수 있습니다. `bash run.sh --host 0.0.0.0 --port 8000`으로 수신 주소를 지정할 수도 있습니다. 다른 PC의 카메라·마이크 접속에는 HTTPS 구성이 필요하므로 Ubuntu 운영 서버는 위 Docker + Caddy 구성을 사용하세요.

## 회의록과 데이터

- 음성은 서버에서 디코딩·인식하며 외부 AI API로 전송하지 않습니다. 영상·음성 원본 녹화 파일은 저장하지 않습니다.
- 전사와 수동 기록은 SQLite에 저장됩니다. Docker는 `meeting-data` 볼륨에 보관합니다.
- 자동 정리는 **발언자별 묶기와 키워드 기반 후보 추출**입니다. 생성형 AI에 의한 의미 요약·교정은 아직 연결하지 않았습니다. 원문을 보존하고 부정문·미합의 내용을 확정 결정으로 자동 승격하지 않습니다.
- 발언자 이름은 로그인 인증된 실명이 아닌 입장 시 입력한 표시 이름입니다.
- 브라우저 화면에는 최근 200개 기록을 표시하고, 내보내기에는 해당 방의 전체 기록을 포함합니다.
- 참가 토큰은 브라우저 메모리에만 두고 퇴장 시 폐기합니다. 방장은 공유 접속 ID와 별도의 참가 토큰으로 권한을 확인합니다.
- 종료된 방에 재입장하는 기능은 없습니다. 기록은 관리자용 스크립트로 복구할 수 있습니다.

```bash
python scripts/export_minutes.py --db data/meetings.db --list
python scripts/export_minutes.py --db data/meetings.db --room-id ROOM_ID --output minutes.md
```

서버 재시작 시 진행 중인 방은 종료되며, 화이트보드는 메모리에만 있습니다. 새 방을 만들면 새 접속 ID가 발급됩니다. 회의록 DB의 백업·보관 기간·삭제 정책은 운영 단계에서 정해야 합니다.

## 구조

```text
app/main.py           HTTP / WebSocket / 방과 WebRTC 연결 관리
server.py             실행 진입점 (수신 주소, 포트, 환경 파일 설정)
app/domain.py         방장·발표권 규칙, SQLite, 회의록 정리
app/media.py          서버 음성 차단, Vosk 실시간 전사
static/               한국어 브라우저 UI (HTML/CSS/JavaScript)
scripts/              한국어 모델 설치, 기록 내보내기, 브라우저 검증
tests/                권한·방·기록·실제 WebRTC 미디어 테스트
deploy/               HTTPS(Caddy), NAT 중계(coturn) 예제
Dockerfile            Python 서버 이미지
compose.yaml          Ubuntu 서버 실행 구성
```

각 클라이언트는 서버로 오디오 1개와 영상 1개를 전송하고, 다른 참석자별 수신 연결을 만듭니다. 화면 공유는 카메라 영상 트랙을 교체합니다. Python 서버가 미디어를 실제 중계하므로 클라이언트 간 직접 연결에 의존하지 않습니다. aiortc는 수신 영상을 다시 인코딩하므로 인원이 증가하면 CPU·네트워크 비용이 빠르게 늘어납니다. 대규모 사용은 SFU 전환을 검토해야 합니다.

## 검증

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
# 서버를 실행한 상태에서, 시스템 Chrome이 설치된 PC:
python scripts/browser_smoke.py
```

현재 Windows PC의 기존 환경으로 검증하려면 이 디렉토리에서 `..\.venv\Scripts\python.exe -m pytest -q`를 사용합니다.

자동 테스트는 기본 음소거, 권한 검증, 단일 발표권/자유 발언, 방장 이전, 화이트보드 동기화·검증, 회의록 접근 제한과 저장, 실제 WebRTC 영상/음성 수신 및 발표권 전환 후 음성 차단을 확인합니다. 실제 카메라·마이크 품질, 화면 선택 창과 파일 공유, NAT/TURN 및 Ubuntu Docker 실행은 배포 환경에서 별도 확인해야 합니다.

참고한 공식 문서: [aiortc MediaRelay](https://aiortc.readthedocs.io/en/latest/helpers.html), [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/), [Vosk 한국어 모델](https://alphacephei.com/vosk/models).
