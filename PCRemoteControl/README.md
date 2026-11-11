# PCRemoteControl v0.2.0

Windows 10/11 PC 간 화면 보기와 키보드·마우스 제어를 위한 원격제어 프로그램입니다. 하나의 클라이언트에서 HOST 또는 TARGET 역할을 선택합니다.

## 주요 기능

- 화면은 WebRTC VP8 미디어로 전송하고, 인증·입력 명령·세션 신호는 Relay와의 TLS/TCP 연결로 처리합니다.
- 화면 미디어는 ICE 연결과 DTLS-SRTP로 보호됩니다. NAT/방화벽 환경에 따라 STUN만으로 연결되지 않을 수 있으며, 이 경우 TURN 서버를 설정해야 합니다.
- 주 모니터를 최대 가로 1600px로 축소하고 약 20fps를 목표로 캡처합니다. 실제 프레임률은 캡처, 인코딩, 네트워크 상태에 따라 달라집니다.
- 원격 마우스 이동·버튼·휠, 키보드 입력, 전체 화면(F11)을 지원합니다. 오디오, 파일 전송, 클립보드, 다중 모니터 선택은 지원하지 않습니다.
- WebRTC 미디어 인코딩·디코딩에 양쪽 PC의 FFmpeg 8.1 Shared 네이티브 라이브러리가 필요합니다. 라이브러리는 클라이언트 EXE에 포함되지 않습니다.

## 연결 및 인증

```text
HOST ── TLS/TCP ── Relay ── TLS/TCP ── TARGET
HOST ═══════ WebRTC VP8 미디어 경로 ═══════ TARGET
```

1. HOST와 TARGET은 Relay에 연결합니다. 비밀번호 인증 후 서버에 고정된 이메일 주소로 전송된 6자리 코드를 입력해야 연결이 완료됩니다.
2. HOST에서 온라인 TARGET을 선택하고 **원격접속**을 누릅니다. TARGET 화면에 접속 상태가 표시되며 별도의 세션별 승인 대화상자는 없습니다.
3. HOST 화면을 클릭하면 원격 입력이 활성화됩니다. TARGET에서 연결을 중지하거나 종료하면 화면 공유와 제어가 끝납니다.

이메일 코드는 `forlovesea@gmail.com`으로 발송되며 5분 동안 유효하고 한 번만 사용할 수 있습니다. 서버에 SMTP를 설정하지 않았거나 발송에 실패하면 연결이 허용되지 않습니다. 자동 재연결 시에도 새 이메일 인증이 필요합니다.

## Windows 클라이언트 실행

1. HOST와 TARGET 모두에 64비트 FFmpeg 8.1 Shared 라이브러리를 설치합니다.
2. [PCRemoteControl-v0.2.0.exe](./release/v0.2.0/PCRemoteControl-v0.2.0.exe)를 실행하고 Relay 주소, 포트, 비밀번호를 설정합니다. TARGET에는 표시할 PC 이름도 지정합니다.
3. 두 PC에서 **서버 연결**을 누르고 각각 이메일 인증을 완료합니다.
4. HOST의 TARGET 목록에서 대상 PC를 골라 **원격접속**을 누릅니다.

기본 Relay 주소는 `61.105.141.21`, 포트는 `61000`입니다. 실제 서버 인증서에 포함된 DNS 이름을 사용하세요. IP 주소로 직접 연결하려면 서버 인증서에 해당 IP SAN이 있어야 합니다. TLS 인증서 검증을 끄는 옵션은 없습니다.

TARGET 역할만 실행하려면 다음 인수를 사용할 수 있습니다.

```powershell
.\PCRemoteControl-v0.2.0.exe --target
```

설정과 기기 ID는 `%LOCALAPPDATA%\PCRemoteControl\settings.json`에 저장됩니다. TARGET 비밀번호는 자동 복구용으로 `%LOCALAPPDATA%\PCRemoteControl\target-password.bin`에 Windows DPAPI로 암호화해 저장합니다. 클라이언트 로그는 `%LOCALAPPDATA%\PCRemoteControl\client.log`에 기록되며 크기가 512000바이트를 넘으면 `.old` 파일로 회전합니다. 비밀번호, 인증 코드, 화면 내용은 로그에 기록하지 않습니다.

클라이언트는 로그인된 Windows 데스크톱에서 실행해야 합니다. Windows 잠금·로그인 화면, UAC 보안 데스크톱, Ctrl+Alt+Del 및 일반 권한으로 실행한 TARGET에서의 관리자 권한 앱 제어는 지원하지 않습니다.

## STUN/TURN 설정

기본 ICE 설정은 Cloudflare STUN입니다. TURN이 필요한 네트워크에서는 HOST와 TARGET 양쪽 Windows 사용자 환경에 `PCREMOTE_ICE_SERVERS`를 설정하고 앱을 다시 실행하세요. TURN 주소와 자격 증명은 TURN 운영자가 제공한 값을 사용합니다.

```powershell
[Environment]::SetEnvironmentVariable(
  "PCREMOTE_ICE_SERVERS",
  '[{"urls":"stun:stun.cloudflare.com:3478"},{"urls":"turn:turn.example.com:3478?transport=udp","username":"<user>","credential":"<credential>"}]',
  "User")
```

값은 JSON 배열이며 각 항목은 `urls`를 포함하고, TURN 인증이 필요한 경우 `username`과 `credential`을 함께 포함해야 합니다. 최대 16개 서버를 지정할 수 있습니다. 실제 자격 증명을 소스 코드나 로그에 기록하지 마세요. TURN을 이용하면 미디어 패킷이 TURN 사업자를 통과하지만 DTLS-SRTP로 암호화됩니다.

## Relay 설치 및 운영

Relay는 Python 3.8 이상과 표준 라이브러리를 사용합니다. 공개 DNS 이름에 유효한 TLS 인증서와 키를 준비하고 Ubuntu 서버에서 설치하세요. 다음 예시는 GitHub 저장소에 접근할 수 있는 경우입니다.

```sh
sudo apt-get update
sudo apt-get install -y git python3 ca-certificates
git clone https://github.com/forlovesea/work.git
cd work/PCRemoteControl
sudo sh server/install.sh /path/to/fullchain.pem /path/to/privkey.pem
```

설치 스크립트는 `pcremote-relay`라는 별도 systemd 서비스만 설치·재시작하며 기존 스마트폰용 Relay 서비스는 변경하지 않습니다. TCP 61000이 이미 사용 중이면 설치를 중단합니다. 설치 후 서버 방화벽과 클라우드 보안 그룹에서 TCP 61000을 허용하세요. UFW를 사용하는 경우:

```sh
sudo ufw allow 61000/tcp
```

설치 시 `/etc/pcremote/relay.env`에 `PCREMOTE_PASSWORD`가 없으면 예시용 기본값 `jjh1234`가 생성됩니다. 공개 서버를 운영하기 전에 반드시 강한 비밀번호로 변경하고, HOST와 TARGET에도 같은 값을 입력하세요. 비밀번호를 바꾼 뒤에는 서비스를 재시작합니다.

```sh
sudo nano /etc/pcremote/relay.env
sudo systemctl restart pcremote-relay
```

이메일 인증을 사용하려면 `/etc/pcremote/relay.env`에 STARTTLS를 지원하는 SMTP 계정 정보를 설정하세요. 수신 주소는 `forlovesea@gmail.com`으로 고정되어 있습니다.

```ini
PCREMOTE_PASSWORD=replace-with-a-strong-password
PCREMOTE_SMTP_HOST=smtp.example.com
PCREMOTE_SMTP_PORT=587
PCREMOTE_SMTP_USER=sender@example.com
PCREMOTE_SMTP_PASSWORD=replace-with-smtp-credential
PCREMOTE_SMTP_FROM=sender@example.com
```

`PCREMOTE_SMTP_FROM`은 선택 항목이며 생략하면 SMTP 사용자 주소를 발신 주소로 사용합니다. 환경 파일은 비밀정보이므로 서버에서 권한을 제한하고 저장소에 올리지 마세요. 설정 후 서비스를 재시작하세요. 이메일 요청은 IP별 60초 간격 및 서버 전체 최소 5초 간격으로 제한됩니다.

서비스 상태와 로그:

```sh
sudo systemctl --no-pager --full status pcremote-relay
sudo journalctl -u pcremote-relay -f
```

Relay 업데이트는 저장소에서 `git pull --ff-only origin main`을 실행한 뒤 다음과 같이 적용합니다. Relay 재시작 중 연결된 세션은 종료되며 TARGET은 자동으로 재연결을 시도합니다.

```sh
sudo sh server/install.sh /etc/pcremote/fullchain.pem /etc/pcremote/privkey.pem
```

TLS 인증서가 갱신된 뒤에도 Relay 서비스를 재시작해야 새 인증서를 사용합니다. NAT 환경에서 미디어 연결이 안 되면 별도 TURN 서비스를 구성하고 위의 ICE 설정을 양쪽 PC에 적용하세요. Relay 포트 개방만으로 모든 WebRTC 미디어 경로가 보장되는 것은 아닙니다.

## TARGET 자동 복구 (선택)

`build.ps1 -IncludeWatchdog`로 Watchdog를 함께 빌드할 수 있습니다. 생성된 `PCRemoteControl.Watchdog-v0.2.0.exe`를 클라이언트와 같은 폴더에 두고 실행하세요. Watchdog는 TARGET만 감시하며 HOST는 감시하지 않습니다.

- 비정상 종료 시 TARGET을 다시 실행하고 Relay 재연결을 시도합니다. 인증이 다시 필요하면 이메일 코드를 입력해야 합니다.
- TARGET에서 **연결 중지**를 누르면 자동 복구를 멈춥니다. 정상 종료한 TARGET은 자동으로 다시 실행하지 않습니다.
- Watchdog는 이미 수동 실행 중인 TARGET을 인계받지 않습니다. TARGET 비밀번호는 현재 Windows 사용자 계정에 종속된 DPAPI로 암호화 저장됩니다.
- Watchdog 자체의 장애, Windows 로그아웃·재부팅, 절전 또는 전원 꺼짐은 복구하지 않습니다. 로그인 시 자동 실행은 사용자가 별도로 설정해야 합니다.

## 빌드 및 테스트

필요한 도구: .NET 8 SDK, Windows x64 빌드 환경, Relay 테스트용 Python 3.8 이상.

```powershell
dotnet build .\Client\PCRemoteControl.csproj -c Release
dotnet run --project .\FrameTests\FrameTests.csproj -c Release
dotnet run --project .\RecoveryTests\RecoveryTests.csproj -c Release
python -m unittest discover -s server -v
.\build.ps1
```

배포 EXE와 SHA-256 목록은 `release/v0.2.0/`에 생성됩니다. 기본 배포 빌드는 클라이언트 단일 EXE를 만들지만 FFmpeg 8.1 Shared 네이티브 라이브러리는 포함하지 않습니다. Watchdog 포함 빌드:

```powershell
.\build.ps1 -IncludeWatchdog
```

릴리스 의존성의 라이선스 조건도 확인하세요. SIPSorcery에는 추가 사용 제한이 명시되어 있고, SIPSorceryMedia.FFmpeg는 LGPL-2.1-only 라이선스를 사용합니다.

## 검증 범위와 제한

자동 테스트는 화면 프레임 변환, 클라이언트 복구 정책, Relay 인증 및 메시지 처리, WebRTC signaling 전달 등을 검증합니다. 실제 두 PC 간 연결, 다양한 NAT 조합, TURN 서비스, FFmpeg 인코딩·디코딩을 포함한 운영 환경 검증은 배포 환경에서 별도로 수행해야 합니다.
