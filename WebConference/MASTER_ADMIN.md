# Master 비밀번호 인증과 방 관리

화면 오른쪽 위 **Master 인증**을 누르고 Master 키를 입력합니다. 성공하면 버튼이 **Master 관리**로 바뀝니다. 일반 방장의 이메일 승인과 별개이며, 이메일 승인만으로는 전체 방 관리 권한을 얻지 않습니다.

## Master 기능

- 이메일 승인 없이 새 회의를 만들고 시작할 수 있습니다.
- Master 관리에서 진행 중인 모든 방과 참석자를 조회하고 원하는 방에 입장할 수 있습니다.
- 정원이 찬 방도 Master용 추가 1자리까지 입장할 수 있습니다. 이 자리까지 찬 경우에는 관리 화면에서 참석자를 퇴장시키거나 방을 종료할 수 있습니다.
- 방 안의 참석자 목록 또는 Master 관리 화면에서 **강제 퇴장**할 수 있습니다. 해당 사용자의 연결과 접속 토큰을 폐기하고 방의 접속 ID와 초대 링크를 새로 발급합니다. 남은 참석자들은 새 초대 링크를 사용해야 합니다.
- **방 삭제**를 누르면 모든 참석자의 연결을 종료하고 방을 폐쇄합니다. 기존 접속 ID로는 들어올 수 없습니다. 저장된 회의록은 DB에 보존됩니다.

강제 퇴장은 해당 연결을 대상으로 합니다. 이 서비스는 일반 참석자에게 계정 로그인을 요구하지 않으므로, 퇴장된 사람이 다른 사람에게 새 초대 ID를 받아 다른 신원으로 입장하는 것까지 영구 차단하지는 않습니다.

Master 인증은 최대 1시간 유지됩니다. 새로고침·탭 종료·서버 재시작·Master 로그아웃 후에는 다시 인증해야 합니다. 관리 키와 토큰은 브라우저 저장소에 저장하지 않습니다. 키가 바뀌면 기존 관리 인증은 다음 요청부터 즉시 거부되며 화면은 약 15초 간격으로 이를 확인합니다.

## Ubuntu 서버 설치 및 최초 키 등록

회의가 없는 시간에 기존 `WebConference/RelayServer` 폴더에서 실행합니다. 설치는 `moa`를 재시작하므로 현재 화상회의는 종료됩니다.

```bash
git pull --ff-only
sudo bash deploy/native/install.sh /opt/moa/python/3.12.15/bin/python3.12
sudo /opt/moa/current/.venv/bin/python /opt/moa/current/scripts/set_master_key.py
```

마지막 명령의 `New Master key`와 `Confirm Master key`에 사용할 키를 두 번 입력합니다. 최초 등록 시 요청한 키를 입력하면 됩니다. 입력한 문자는 화면에 표시되지 않습니다. 실제 키나 해시는 GitHub에 포함하지 않습니다.

키 해시는 `/etc/moa/master-key.json`에 `root:moa`, 권한 `640`으로 저장됩니다. 기존 키 파일은 프로그램 업데이트 때 유지됩니다. 기본 경로를 바꾸려면 `/etc/moa/moa.env`에 `MASTER_KEY_FILE=/절대/경로/master-key.json`을 지정하고, 설정 명령에도 같은 `--path`를 전달하세요. 파일을 읽을 수 있는 권한과 systemd 경로 접근 권한이 필요합니다.

```bash
curl --noproxy '*' -fsS http://127.0.0.1:8000/api/config
```

`"master_password_ready":true`를 확인한 후 브라우저를 새로고침하여 Master 인증을 진행합니다. Master 직접 생성에는 SMTP가 필요하지 않습니다. 일반 사용자의 회의 생성에는 기존 [이메일 승인 설정](MASTER_APPROVAL.md)이 필요합니다.

## 키를 잊었거나 변경할 때

서버에 SSH로 접속한 뒤 **같은 명령**을 실행합니다. 기존 키를 몰라도 서버 관리자 권한으로 재설정할 수 있습니다.

```bash
sudo /opt/moa/current/.venv/bin/python /opt/moa/current/scripts/set_master_key.py
```

새 키를 두 번 입력하면 즉시 적용됩니다. **서비스를 재시작할 필요가 없습니다.** 기존 Master 관리 인증은 해제되지만 진행 중인 화상회의 연결은 유지됩니다. 키는 12~256자를 사용할 수 있습니다.

키를 명령줄 인수에 직접 넣는 옵션은 제공하지 않습니다. 셸 명령 기록에 비밀번호를 남기지 않기 위한 방식입니다. Windows 개발 환경에서는 `python scripts/set_master_key.py`를 실행하며 기본 파일은 `RelayServer/data/master-key.json`입니다.

## 권한과 검증

키는 무작위 salt를 사용한 PBKDF2-HMAC-SHA256 600,000회 해시로 저장합니다. 로그인은 IP별 10분당 5회, 전체 30회로 제한하며 동일 서버에서 재시작해도 제한 기록은 유지됩니다. 키를 재설정하면 새 키로 로그인할 때 이전 시도 제한도 초기화됩니다. [OWASP 비밀번호 저장 안내](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

서버가 모든 Master 요청의 세션·만료·키 변경 여부를 확인합니다. 이름을 Master로 입력하거나 일반 방장 토큰을 보내는 것으로는 관리할 수 없습니다. 생성·입장·강제 퇴장·방 삭제 작업은 DB `master_audit`에 시각과 대상 ID를 남깁니다.

`python scripts/browser_master_smoke.py`는 별도 로컬 테스트 서버와 임시 테스트 키로 실제 브라우저의 생성·입장·강제 퇴장·미디어 종료·방 삭제·키 변경·모바일 화면을 검증합니다. 실제 이메일은 보내지 않습니다.
