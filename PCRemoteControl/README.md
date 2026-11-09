# PCRemoteControl

## 이메일 인증 (필수)

HOST와 TARGET 모두 **비밀번호 확인 → `forlovesea@gmail.com`으로 전송된 6자리 코드 입력 → 서버 연결 완료** 순서로 접속합니다. 인증 통신을 위한 TLS 연결은 먼저 열리지만, 이메일 인증 전에는 TARGET 등록·목록 조회·원격제어가 허용되지 않습니다. 코드 유효시간은 5분이며 해당 연결에서 한 번만 사용할 수 있습니다. 잘못 입력하거나 취소·만료된 경우 서버 연결을 다시 눌러 새 코드를 요청하세요. 발송은 IP당 60초에 한 번, 서버 전체에서 최소 5초 간격으로 제한합니다.

서버와 클라이언트를 함께 업데이트해야 합니다. 새 클라이언트는 이메일 인증이 없는 이전 서버에 연결하지 않습니다. 새 서버에서도 이전 클라이언트는 인증을 완료할 수 없습니다. SMTP 설정 누락이나 발송 실패 시 연결을 허용하지 않습니다.

서버의 `/etc/pcremote/relay.env`에 기존 `PCREMOTE_PASSWORD`를 유지하면서 아래 값을 추가하세요. STARTTLS를 지원하는 SMTP 서버와 발송 계정을 사용합니다. 수신 주소는 서버 코드에 고정되어 있으며 클라이언트에서 바꿀 수 없습니다.

```ini
PCREMOTE_SMTP_HOST=smtp.example.com
PCREMOTE_SMTP_PORT=587
PCREMOTE_SMTP_USER=sender@example.com
PCREMOTE_SMTP_PASSWORD="replace-with-smtp-credential"
PCREMOTE_SMTP_FROM=sender@example.com
```

`PCREMOTE_SMTP_FROM`을 생략하면 발송 계정 주소를 사용합니다. SMTP 비밀값은 서버 환경 파일에만 넣고 저장소나 클라이언트에 넣지 마세요. 설정 후 `sudo systemctl restart pcremote-relay`를 실행하세요. 설치 스크립트는 기존 환경 파일을 보존합니다. 실제 메일 수신 여부는 운영 SMTP 설정 후 확인해야 합니다.

**자동 복구 동작 변경:** TARGET의 자동 시작·네트워크 재연결 때도 새 이메일 코드를 입력해야 하므로 완전한 무인 재연결은 지원하지 않습니다. 인증 오류나 취소 시 자동 재시도를 멈춥니다. 서버 연결 버튼으로 다시 시작하세요. 아래 기존 자동 복구 설명에도 이 조건이 적용됩니다.

검증: `python -m unittest discover -s server -v` (실제 메일 발송 없이 테스트).

Windows 10/11 PC 간 원격 화면 보기 및 키보드·마우스 제어 프로그램입니다. HOST와 TARGET은 동일 실행 파일에서 역할을 선택합니다. 기존 `RemoteControl` 파일이나 서비스를 변경하지 않습니다.

## 구성

`HOST → TLS/TCP 61000 Relay ← TLS/TCP 61000 TARGET`

- TARGET에서 연결 유지 시작 후 10초마다 heartbeat, 35초 수신 제한, 단절 시 5초 후 재연결합니다.
- 양쪽 모두 서버로 외부 연결을 하므로 TARGET의 NAT 포트 포워딩이 필요 없습니다. Relay 공인 주소와 서버 TCP 61000 인바운드 허용이 필요합니다.
- HOST 비밀번호 인증 후 TARGET 목록을 표시하며 5초마다 갱신합니다. 기본 비밀번호는 `jjh1234`입니다.
- 대상 선택 → 원격접속 → 화면 클릭으로 제어합니다. 대상당 HOST 한 대만 접속할 수 있습니다.
- 창 크기에 맞춘 화면, F11 전체 화면, 전체 화면에서 Esc 복귀를 지원합니다.
- TARGET 연결 중지 또는 앱 종료 시 공유와 제어를 중지합니다. HOST 연결만 종료하면 TARGET은 다시 대기합니다.
- TLS 서버 인증서 체인과 주소를 검증합니다. 검증 우회 옵션은 없습니다. Relay는 신뢰하는 관리자가 운영하며 화면/입력이 Relay에서 복호화되는 구조입니다.

## 실행

1. 공인 Relay를 아래 절차로 설치합니다.
2. TARGET PC에서 `PCRemoteControl-v0.1.1.exe`를 실행하고 TARGET 역할, Relay 인증서에 맞는 DNS 주소, 포트 `61000`, 비밀번호, PC 이름을 입력합니다.
3. **서버 연결**을 누릅니다. 이 동작은 인증된 HOST의 화면 보기와 입력 제어를 허용합니다. TARGET 창에 접속 상태가 표시됩니다.
4. HOST PC에서 같은 프로그램을 HOST 역할로 실행하고 같은 주소·포트·비밀번호로 연결합니다.
5. 목록에서 TARGET을 선택하고 **원격접속**을 누릅니다.

`PCRemoteControl-v0.1.1.exe --target`으로 TARGET 역할을 바로 선택할 수 있습니다. 앱은 사용자가 로그인한 데스크톱에서 실행해야 합니다. 로그인 전 Windows 서비스, 자동 시작 등록, 절전 방지는 구현하지 않았습니다. 서버 주소·PC 이름·기기 ID는 `%LOCALAPPDATA%/PCRemoteControl/settings.json`에 보관합니다. 기본 서버 주소는 `61.105.141.21`이며 변경 가능합니다. IP 직접 접속 시 인증서에 해당 IP SAN이 필요합니다.

## TARGET 자동 복구 감시 프로그램

배포 폴더의 **Start-TARGET.cmd** 또는 **PCRemoteControl.Watchdog-v0.1.1.exe**를 실행하세요. 감시 프로그램이 같은 폴더의 TARGET을 실행하고 Relay 연결을 자동으로 시작합니다. 최초 실행 전 주소·비밀번호를 바꿔야 한다면 `PCRemoteControl-v0.1.1.exe --target`으로 설정하고 서버 연결을 한 번 누른 후 종료하세요.

- 프로세스와 UI heartbeat를 2초마다 확인합니다. UI heartbeat는 네트워크 연결 상태와 별개입니다.
- 비정상 종료 시 5초 후 재실행합니다. 반복 장애 시 10/20/40/60초로 간격을 늘리며, 5분 정상 동작 후 초기화합니다.
- 실행 중 UI heartbeat가 60초 넘게 없으면 자신이 실행한 TARGET 프로세스만 종료하고 재실행합니다. 최초 실행에 60초 유예를 줍니다.
- TARGET에서 **연결 중지**를 누르면 자동 복구를 일시 중단합니다. TARGET에서 **서버 연결**을 누르면 다시 감시합니다. TARGET 창을 정상적으로 닫으면 자동 재실행을 중단하며, 감시 창의 **감시 시작**으로 다시 실행할 수 있습니다.
- 감시 창의 **감시 중지** 또는 창 닫기는 감시만 중지합니다. 실행 중인 TARGET은 그대로 남습니다. 원격접속을 차단하려면 TARGET에서 연결 중지를 누르세요.
- 이미 수동 실행한 TARGET은 자동으로 인계받거나 종료하지 않습니다. 기존 TARGET을 종료한 다음 감시 시작을 누르세요. HOST는 감시하지 않습니다.
- TARGET 비밀번호는 자동 복구를 위해 `%LOCALAPPDATA%/PCRemoteControl/target-password.bin`에 Windows DPAPI로 암호화 저장합니다. 같은 Windows 사용자 계정에서만 복호화합니다. HOST 비밀번호는 저장하지 않습니다.
- 로그: `%LOCALAPPDATA%/PCRemoteControl/watchdog.log` (512KB 순환). 비밀번호는 로그나 명령줄에 넣지 않습니다.

감시 프로그램 자체의 장애, Windows 로그아웃/재부팅, 절전/전원 꺼짐은 복구 대상이 아닙니다. 로그인 시 자동 실행을 원하면 배포 폴더를 고정한 다음 `PCRemoteControl.Watchdog-v0.1.1.exe`의 바로가기를 `shell:startup`에 직접 등록할 수 있습니다. 자동 시작 등록은 이번 작업에서 수행하지 않았습니다.

복구 정책/암호화 검사: `dotnet run --project RecoveryTests/RecoveryTests.csproj -c Release`. 실제 PC에서는 TARGET 연결 중 작업 관리자로 TARGET만 강제 종료한 뒤 재실행과 Relay 복구를 확인하고, 정상 종료와 연결 중지는 재실행되지 않는지 확인하세요. 이 UI/프로세스 실환경 검증은 아직 수행하지 않았습니다.

## 빌드

.NET 8 SDK로 다음을 실행합니다.

```powershell
dotnet build .\Client\PCRemoteControl.csproj -c Release
.\build.ps1
```

배포 출력은 `release/v0.1.1/win-x64/PCRemoteControl-v0.1.1.exe`입니다. build.ps1의 자체 포함 배포에는 런타임 팩 다운로드가 필요할 수 있습니다. 일반 build 출력은 `.NET 8 Desktop Runtime x64`가 설치된 PC에서 실행합니다.

## Ubuntu Relay 설치

GitHub에서 내려받아 설치하는 방법입니다. 이미 저장소가 있다면 해당 저장소에서 `git pull --ff-only origin main`을 실행합니다. 명령은 Ubuntu SSH 터미널에서 실행하세요.

```sh
sudo apt-get update
sudo apt-get install -y git python3 ca-certificates
git clone https://github.com/forlovesea/work.git
cd work/PCRemoteControl
sudo sh server/install.sh /path/to/fullchain.pem /path/to/privkey.pem
```

인증서 경로를 실제 파일로 바꾸세요. 설치 스크립트는 기본 포트 61000의 충돌을 검사하고 PC용 서비스만 설치합니다. 재실행 시 기존 비밀번호를 유지하며 서버 코드 직전 버전을 `relay.py.previous`로 보관합니다. 인증서 자동 발급과 방화벽 변경은 하지 않습니다. 설치가 끝난 후 필요한 방화벽 규칙을 추가하세요.

업데이트는 `git pull --ff-only origin main` 후 `sudo sh server/install.sh /etc/pcremote/fullchain.pem /etc/pcremote/privkey.pem`으로 적용합니다. PC 원격 세션은 서비스 재시작 때 끊기며 TARGET이 자동으로 재접속합니다.

Ubuntu 20.04는 2025년 5월 표준 지원이 종료되었으므로 운영 서버의 보안 업데이트는 Ubuntu Pro/ESM 등 유지보수 상태를 확인하세요. [Ubuntu 공식 안내](https://ubuntu.com/20-04)

Python 3.8 이상, 표준 라이브러리만 사용합니다. 아래 명령은 새 PC용 서비스만 설치합니다. 인증서는 서버 DNS 이름과 일치하는 유효한 인증서 파일로 준비하세요. 기존 스마트폰 서비스의 파일을 덮어쓰지 마세요.

```sh
sudo useradd --system --no-create-home --shell /usr/sbin/nologin pcremote
sudo install -d -m 755 /opt/pcremote
sudo install -d -o root -g pcremote -m 750 /etc/pcremote
sudo install -m 644 server/relay.py /opt/pcremote/relay.py
sudo install -o root -g pcremote -m 640 /path/to/fullchain.pem /etc/pcremote/fullchain.pem
sudo install -o root -g pcremote -m 640 /path/to/privkey.pem /etc/pcremote/privkey.pem
printf 'PCREMOTE_PASSWORD=jjh1234\n' | sudo tee /etc/pcremote/relay.env > /dev/null
sudo chown root:pcremote /etc/pcremote/relay.env
sudo chmod 640 /etc/pcremote/relay.env
sudo install -m 644 server/pcremote-relay.service /etc/systemd/system/pcremote-relay.service
sudo systemctl daemon-reload
sudo systemctl enable --now pcremote-relay
sudo systemctl status pcremote-relay
```

사용 중인 방화벽과 클라우드 보안 그룹에서 TCP 61000만 추가 허용하세요. UFW 사용 시 `sudo ufw allow 61000/tcp`. 기존 55000 포트나 `remotecontrol-relay` 서비스는 변경하지 않습니다. 실제 서버에서 61000을 다른 서비스가 사용하는지는 설치 전에 `sudo ss -ltnp`로 확인하세요. 앱과 서버는 스마트폰용 예약 범위 55000~60000 사용을 거부합니다.

비밀번호 변경: `/etc/pcremote/relay.env`의 `PCREMOTE_PASSWORD`를 바꾸고 `sudo systemctl restart pcremote-relay` 후 양쪽 앱에 새 비밀번호를 입력합니다. 기본 비밀번호를 아는 사람은 등록된 TARGET을 제어할 수 있으므로 공인 배포 시 변경을 권장합니다. 잘못된 인증은 IP별 60초 내 10회까지 허용됩니다. 전체 연결 상한은 256개입니다.

인증서 갱신 시 PC용 경로의 인증서도 갱신하고 `pcremote-relay`만 재시작하세요. 로그는 `sudo journalctl -u pcremote-relay -f`로 확인합니다.

## 지원 범위와 검증

- 주 모니터를 최대 가로 1600px JPEG, 최대 약 8fps로 전송합니다. 영상/게임용 고성능 코덱, 오디오, 파일 전송, 클립보드, 다중 모니터 선택은 포함하지 않습니다.
- 마우스 이동/좌우·가운데 버튼/휠, 가상 키코드 기반 키보드 입력을 지원합니다. 한글 입력은 TARGET의 입력기 상태에 따릅니다. F11은 로컬 전체 화면 키이며 시스템 예약 키 조합은 완전 전달하지 않습니다.
- Windows 잠금 화면, 로그인 화면, UAC 보안 데스크톱, Ctrl+Alt+Del은 지원하지 않습니다. 일반 권한 TARGET은 관리자 권한 앱을 제어할 수 없습니다. [Microsoft SendInput 문서](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)의 권한 제한을 따릅니다.
- TLS는 [.NET SslStream](https://learn.microsoft.com/en-us/dotnet/api/system.net.security.sslstream)을 사용합니다.

```sh
cd server
python -m unittest -v test_relay
```

자동 테스트는 로컬 Relay 인증, 중복 ID, 목록, 세션 연결, 사용 중 거부, 프레임·입력 전달, 연결 종료와 크기 제한을 검증합니다. 테스트 전송 자체는 루프백 평문이며 운영 서버는 TLS만 허용합니다.

실제 배포 후 확인할 항목: Windows 10/11 각각에서 캡처·마우스·키보드·전체 화면, 서로 다른 NAT의 두 PC 연결, 네트워크 단절/복구, TLS 인증서 오류 거부, TARGET 중지 후 입력 해제, 기존 스마트폰 서버 정상 동작. 이 실환경 검증과 공인 서버 배포는 아직 수행하지 않았습니다.
