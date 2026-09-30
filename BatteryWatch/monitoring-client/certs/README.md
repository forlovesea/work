# BatteryWatch TLS 인증서 배포

서버 주소: `61.105.141.21`, TCP 업로드 포트: `9443`.

## 저장소에 포함된 공개 인증서

- `BatteryWatch/server/certs/server.pem`: 위 IP가 SAN에 포함된 서버 인증서.
- `BatteryWatch/server/certs/ca.pem`: 서버 인증서를 발급한 사설 CA 공개 인증서.
- `BatteryWatch/monitoring-client/certs/batterywatch-ca.pem`: 클라이언트용 CA 공개 인증서 사본.

서버 인증서는 2027-09-30 22:17:11 UTC(한국 시간 2027-10-01 07:17:11)까지 유효합니다.
CA 공개 인증서는 클라이언트에 배포할 수 있지만, 개인키와 토큰은 저장소에 포함하지 않습니다.

## 서버 적용

1. 서버에서 `git pull`로 공개 인증서를 받습니다.
2. 최초 한 번, 인증서를 생성한 PC의 `BatteryWatch/server/certs/server-key.pem`을
   SSH/SFTP 등 별도 보안 경로로 서버의 같은 상대 경로에 복사합니다.
   이 인증서와 짝인 기존 개인키가 필요하며 새 키를 생성해서 대체할 수 없습니다.
   `ca-key.pem`은 서버 운영에 필요하지 않으므로 발급 PC에 보관합니다.
3. 기존 `server.local.json`의 수집기 토큰 해시, 장비 권한, DB, API 설정은 유지하면서
   다음 항목만 적용합니다. 실행 중인 서버가 다른 설정 파일을 사용한다면 그 파일에 적용합니다.

```json
{
  "host": "0.0.0.0",
  "port": 9443,
  "tls": {
    "certfile": "certs/server.pem",
    "keyfile": "certs/server-key.pem"
  }
}
```

위 JSON은 변경 항목의 예시이며 전체 설정 파일을 대체하는 내용이 아닙니다.
개인키는 서버 실행 계정만 읽을 수 있도록 권한을 제한합니다.
Linux에서는 소유자를 실행 계정에 맞춘 후 `chmod 600 certs/server-key.pem`을 적용합니다.

4. `BatteryWatch/server` 디렉터리에서 설정을 점검하고 기존 실행 방식에 따라 서버를 재시작합니다.

```bash
python server.py --config server.local.json check
# 기존 서버 프로세스/서비스를 중지한 뒤 실행하거나 해당 서비스를 재시작
python server.py --config server.local.json run
```

5. 서버 방화벽 및 필요한 NAT 설정에서 TCP 9443 접속을 허용합니다.
   조회 API가 활성화되어 있으면 같은 TLS 인증서를 사용하므로 앱의 신뢰 설정도 확인합니다.

`git pull`만으로 개인키·로컬 설정이 생성되거나 실행 중인 서버가 재시작되지는 않습니다.
배포한 서버의 수집기 토큰 및 현장/장비 권한과 클라이언트의 입력값도 일치해야 합니다.

## 모니터링 클라이언트

‘서버 TCP 업로드 설정’에서 다음을 입력하고 저장합니다.

- 서버 IP / 호스트: `61.105.141.21`
- TCP 포트: `9443`
- TLS 암호화 / 인증서 검증: 켜짐
- CA 파일: 해당 PC의 `monitoring-client/certs/batterywatch-ca.pem` 전체 경로
- 토큰, 현장 ID, 장비 ID: 실제 서버에서 허용한 수집기 인증 정보

설정 후 업로드를 켜고 메인 화면 하단의 ACK를 확인합니다.
클라이언트에는 CA 공개 인증서만 필요하며 서버 개인키를 복사하지 않습니다.
