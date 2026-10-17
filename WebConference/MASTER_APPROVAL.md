# Master 이메일 인증

새 회의는 Master `forlovesea@gmail.com`의 승인을 받은 방장만 만들 수 있습니다. 이미 만들어진 방에 참여하는 참석자는 이 승인이 필요하지 않습니다.

단, [Master 비밀번호 인증](MASTER_ADMIN.md)을 마친 관리자는 이메일 승인 없이 직접 방을 만들 수 있습니다. 이메일 승인과 전체 방 관리 권한은 서로 다릅니다.

## 사용 순서

1. 방장이 **내 이름**에 별칭 또는 실명을 입력하고 **새 회의 만들기**를 선택합니다.
2. **방장 연락처**에 연락 가능한 이메일 또는 전화번호를 입력합니다.
3. 오른쪽 **이메일 인증**을 누르면 이름과 연락처, 승인 링크가 Master에게 전송됩니다. 새 회의 시작하기는 비활성 상태로 유지됩니다.
4. Master는 받은 이메일의 링크를 열어 사용자 정보를 확인한 후 **인증완료** 또는 **거절**을 누릅니다. 링크를 여는 것만으로는 승인되지 않습니다.
5. 방장 화면이 약 4초 간격으로 승인 상태를 확인합니다. 승인이 완료되면 **새 회의 시작하기**가 활성화됩니다.

요청 링크는 30분 동안 유효하며, 승인 후에도 30분 안에 회의를 시작해야 합니다. 승인은 새 회의 생성 1회에만 사용됩니다. 이름 또는 연락처를 바꾸면 새 승인을 요청해야 합니다. 같은 탭을 새로고침해도 대기 요청은 유지되지만, 탭을 닫거나 다른 브라우저로 옮기면 다시 요청해야 할 수 있습니다. Master 화면을 새로고침해 링크 정보가 없어졌다면 이메일 링크를 다시 여세요.

## Ubuntu 설정

**SMTP 설정이 없으면 일반 사용자의 새 회의 생성 승인을 요청할 수 없습니다.** Master 비밀번호 인증 후 직접 생성하는 기능은 SMTP와 무관합니다. 업데이트 전에 아래 설정을 준비하세요. 기존 방 참여와 다른 서비스 설정은 변경하지 않습니다. 설치 시 `moa`가 재시작되므로 진행 중인 화상회의는 종료됩니다.

1. 회의가 없는 시간에 기존 다운로드 폴더의 `WebConference/RelayServer`에서 최신 코드를 받습니다.

```bash
git pull --ff-only
sudo nano /etc/moa/moa.env
```

2. 기존 DB·Whisper·포트 설정을 유지하고 아래 값을 추가합니다. Gmail 발송 계정 예시이며 SMTP 제공업체가 다르면 해당 업체의 설정을 사용합니다.

```ini
PUBLIC_BASE_URL=https://61.105.141.21:10443
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=YOUR_SENDER_ACCOUNT@gmail.com
SMTP_PASSWORD="YOUR_APP_PASSWORD"
SMTP_FROM=YOUR_SENDER_ACCOUNT@gmail.com
```

`YOUR_SENDER_ACCOUNT`는 실제 발송 계정으로 바꿉니다. Master 계정 자체를 발송 계정으로 써도 되고 별도 계정을 사용해도 됩니다. 수신자는 항상 `forlovesea@gmail.com`입니다. 비밀번호는 서버 설정 파일에만 입력하고 Git이나 채팅에 올리지 마세요.

Gmail의 앱 비밀번호는 2단계 인증이 설정된 계정에서 사용할 수 있으며 계정 정책에 따라 제공되지 않을 수 있습니다. 일반 로그인 비밀번호 대신 발급받은 앱 비밀번호를 사용하세요. [Google 앱 비밀번호 안내](https://support.google.com/accounts/answer/185833?hl=ko), [Google SMTP 안내](https://support.google.com/a/answer/176600?authuser=2&hl=en).

SSL 방식의 SMTP 서버는 `SMTP_SECURITY=ssl`, `SMTP_PORT=465`를 사용합니다. 평문 SMTP 모드는 제공하지 않습니다. 서버에서 SMTP 제공업체로 나가는 해당 포트 연결이 가능해야 하며 서버의 수신 포트를 추가로 열 필요는 없습니다.

3. 설정 파일 권한을 유지하고 설치합니다.

```bash
sudo chown root:moa /etc/moa/moa.env
sudo chmod 640 /etc/moa/moa.env
sudo bash deploy/native/install.sh /opt/moa/python/3.12.15/bin/python3.12
curl --noproxy '*' -fsS http://127.0.0.1:8000/api/config
```

`master_approval_required: true`, `master_email_ready: true`를 확인합니다. `master_email_ready`는 설정 형식의 준비 상태이며 실제 발송 성공을 뜻하지 않습니다.

4. 브라우저를 새로고침하고 테스트 이름·연락처로 인증을 요청합니다. Master 받은편지함 또는 스팸함에서 메일을 확인하고 승인한 뒤 새 회의가 생성되는지 확인합니다. 실제 발송·수신은 운영 서버에서 이 단계로 검증해야 합니다.

```bash
sudo journalctl -u moa -n 80 --no-pager
```

## 승인과 데이터 처리

- Master 이메일로 보낸 링크의 소유를 확인하는 방식이며 Google 로그인 연동은 아닙니다. 승인 링크를 전달받은 사람도 승인할 수 있으므로 공유하지 마세요.
- 신청자 상태 확인 키와 Master 승인 키는 서로 다릅니다. 신청자는 자신의 상태만 확인할 수 있고 Master 승인 API를 호출할 수 없습니다.
- 승인 키는 URL fragment에 담고 서버 접근 로그에 남는 경로·쿼리에 넣지 않습니다. DB에는 키의 SHA-256 해시만 저장합니다.
- 승인 상태는 DB에 저장되어 서버 재시작 후에도 만료 전까지 유지됩니다. 승인 사용 처리와 회의 저장은 같은 DB 트랜잭션으로 처리됩니다.
- 과도한 메일 발송을 막기 위해 서버 전체 시간당 20회, 접속 IP별 5회, 연락처별 3회로 제한하며 같은 연락처의 재요청에는 최소 60초 간격을 둡니다. 실패한 발송도 횟수에 포함됩니다.
- 이름·연락처는 승인 확인을 위해 DB와 Master 이메일에 저장됩니다. DB의 만료 후 24시간이 지난 요청은 서버 시작 또는 다음 인증 요청 시 정리됩니다. 이메일 사본은 Master가 관리합니다.

## 개발 검증

`python scripts/browser_approval_smoke.py`는 127.0.0.1:18080의 별도 테스트 서버를 실행하고 메일을 메모리에만 수집합니다. 실제 이메일은 발송하지 않습니다. 승인 전 차단, Master 승인, 새로고침, 1회 사용, 거절과 모바일 화면을 검증합니다.
