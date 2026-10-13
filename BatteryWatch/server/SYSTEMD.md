# Ubuntu 20.04 부팅 시 자동 실행

기존 설정과 DB를 그대로 사용하는 systemd 서비스입니다. Python 3.12가 설치되어 현재 서버가 정상 실행되는 환경을 기준으로 합니다. `--debug` 없이 시작하므로 부팅/재시작 시 통신 디버그는 꺼집니다. 비정상 종료 시 5초 후 다시 실행합니다.

## 최초 등록

현재 서버 실행 계정으로 새 터미널을 열고, 기존 `server.py` 폴더로 이동합니다. 가상환경을 사용한다면 기존 실행 때와 같은 가상환경을 먼저 활성화하세요.

```bash
whoami
pwd -P
python3.12 -c 'import sys; print(sys.executable)'
python3.12 server.py check
```

`batterywatch.service`를 편집하여 `User`에는 위 계정, `WorkingDirectory`에는 위 서버 폴더의 절대 경로, `ExecStart`에는 위 Python 실행 파일 및 서버/설정 파일의 절대 경로를 넣으세요. 가상환경을 쓴다면 그 가상환경의 Python 경로를 사용합니다. 경로에 공백이 있으면 해당 경로를 큰따옴표로 감싸세요. 사용자 지정 설정을 사용 중이라면 `server.local.json` 대신 실제 설정 경로를 지정하고, `check`에도 `--config /실제/설정.json`을 하위 명령 앞에 넣으세요.

서비스 계정은 기존 설정·인증서 읽기 및 DB·로그 폴더 쓰기 권한이 있어야 합니다. 기존 서버 실행 계정을 사용하면 기존 파일 권한을 유지할 수 있습니다. 서비스는 셸의 활성화 명령이나 환경변수를 자동으로 상속하지 않습니다. 별도 환경변수에 의존하는 경우 서비스에도 해당 설정을 추가하세요.

먼저 기존 `python3.12 server.py run --debug` 실행 터미널에서 **Ctrl+C로 서버를 종료**하세요. 백그라운드 실행이었다면 동일한 설정으로 `python3.12 server.py stop`을 사용하세요. 같은 DB와 포트로 서버를 중복 실행하지 마세요.

편집한 파일이 있는 서버 폴더에서:

```bash
sudo install -m 644 batterywatch.service /etc/systemd/system/batterywatch.service
sudo systemd-analyze verify /etc/systemd/system/batterywatch.service
sudo systemctl daemon-reload
sudo systemctl enable --now batterywatch.service
sudo systemctl status batterywatch.service --no-pager
sudo journalctl -u batterywatch.service -n 50 --no-pager
```

`verify`에서 오류가 나오면 수정 후 진행하세요. 상태가 `active (running)`이고 로그에 수신 포트가 정상적으로 열렸는지 확인하세요. `enable --now`는 지금 실행하고 다음 부팅에도 자동으로 실행하도록 등록합니다. 이제 터미널을 닫아도 서버는 계속 실행됩니다. Ubuntu 서버에서 실제 서비스 시작 및 재부팅 후 확인해야 설치 검증이 완료됩니다.

## 기존 터미널에서 디버그 보기

동일한 실행 계정으로 기존 서버 폴더에서 실행합니다. 서비스를 켜 둔 상태에서는 `run --debug`로 두 번째 서버를 실행하지 않습니다.

```bash
python3.12 server.py debug on
tail -n 50 -F logs/server.log
```

약 1초 후 상세 통신 로그가 활성화됩니다. `tail`에서 Ctrl+C를 누르면 로그 보기만 끝나고 서비스와 디버그 설정은 유지됩니다. 확인을 마쳤으면 다음 명령으로 디버그를 끄세요.

```bash
python3.12 server.py debug off
```

사용자 지정 설정이라면 서비스와 같은 설정 경로로 `python3.12 server.py --config /실제/설정.json debug on` 또는 `debug off`를 실행하세요. 로그 파일은 그 설정 파일 옆 `logs/server.log`입니다. 서비스 로그는 `sudo journalctl -u batterywatch.service -f`로도 볼 수 있습니다.

## 서비스 관리

```bash
# 재시작 (설정을 다시 읽고 디버그 OFF로 시작)
sudo systemctl restart batterywatch.service

# 일시 중지 / 다시 시작
sudo systemctl stop batterywatch.service
sudo systemctl start batterywatch.service

# 부팅 자동 실행 등록 확인
systemctl is-enabled batterywatch.service

# 자동 실행 해제 및 현재 서비스 중지
sudo systemctl disable --now batterywatch.service
```

systemd로 실행한 서버는 `server.py stop/restart` 대신 `systemctl`로 관리합니다. 서비스 파일 자체를 수정한 경우 `sudo systemctl daemon-reload` 후 재시작하세요.

직접 전경 실행이 필요하면 서비스를 먼저 중지하고 `python3.12 server.py run --debug`를 실행하세요. 종료할 때 Ctrl+C를 누른 뒤 `sudo systemctl start batterywatch.service`로 복귀합니다. 이 수동 실행 중에는 systemd가 서버를 관리하지 않습니다.
