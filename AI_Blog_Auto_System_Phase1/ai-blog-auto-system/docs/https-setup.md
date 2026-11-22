# Windows ↔ Ubuntu HTTPS 연결

Windows/Android → **HTTPS 443 Nginx** → **HTTP 127.0.0.1:8000 Uvicorn** 구조입니다.
서버 내부 HTTP는 정상이며 외부 연결에 TLS를 제공하는 Nginx가 필요합니다.
Uvicorn만 실행한 뒤 주소 앞에 `https://`를 붙여도 TLS가 활성화되지 않습니다.
Windows의 `localhost`는 Ubuntu가 아니라 Windows 자신입니다.

| 환경 | Windows 서버 URL |
|---|---|
| Windows에서 서버도 실행 | `http://127.0.0.1:8000` |
| 원격 Ubuntu 운영 | `https://blog.example.com` |
| SSH 터널로 개발 시험 | `http://127.0.0.1:18000` |

원격 HTTP 허용이나 인증서 검증 해제로 해결하지 않습니다. URL에는 `/api/v1`을 붙이지 않습니다.

## 1. 사전 준비

[운영 배포](build-and-deploy.md)에 따라 ai-blog 서비스를 설치합니다.
아래 명령은 Ubuntu의 프로젝트 루트에서 실행하며 `blog.example.com`은 실제 소유한 도메인으로 바꿉니다.
DNS A 레코드가 서버의 공개 IPv4를 가리켜야 합니다. AAAA를 등록했다면 IPv6도 실제 서버로 연결되어야 합니다.
클라우드 보안 그룹·공유기·방화벽에서 TCP 80(인증서 발급/갱신)과 443(앱)을 허용하고 8000은 공개하지 않습니다.
기존 Nginx 사이트가 있다면 설정을 백업하고 같은 도메인의 중복 server 블록을 제거한 후 적용합니다.

```bash
curl --fail http://127.0.0.1:8000/api/v1/health
sudo apt update
sudo apt install -y nginx certbot
sudo install -d -m 755 /var/www/ai-blog-acme
BLOG_DOMAIN=blog.example.com
```

## 2. 인증서 발급 전 HTTP challenge만 활성화

인증서 파일이 없는 상태에서 최종 TLS 설정을 먼저 적용하면 Nginx가 시작되지 않습니다.
이 bootstrap은 API를 노출하지 않습니다.

```bash
sed "s/blog-monitor.example.com/$BLOG_DOMAIN/g" ubuntu-server/deploy/nginx-bootstrap.conf.example | sudo tee /etc/nginx/sites-available/ai-blog >/dev/null
sudo ln -sfn /etc/nginx/sites-available/ai-blog /etc/nginx/sites-enabled/ai-blog
sudo nginx -t && sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/ai-blog-acme --cert-name "$BLOG_DOMAIN" -d "$BLOG_DOMAIN"
```

Certbot의 이메일·약관 안내를 완료합니다. 실패하면 DNS와 외부 80 포트부터 확인합니다.
이미 인증서가 있다면 `sudo certbot certificates`로 이름과 경로를 확인하고 다음 설정의 경로에 맞춥니다.

## 3. HTTPS 프록시 활성화와 갱신

```bash
sed "s/blog-monitor.example.com/$BLOG_DOMAIN/g" ubuntu-server/deploy/nginx.conf.example | sudo tee /etc/nginx/sites-available/ai-blog >/dev/null
sudo nginx -t && sudo systemctl reload nginx
sudo install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nnginx -t && systemctl reload nginx\n' | sudo tee /etc/letsencrypt/renewal-hooks/deploy/ai-blog-nginx >/dev/null
sudo chmod 755 /etc/letsencrypt/renewal-hooks/deploy/ai-blog-nginx
sudo systemctl enable --now certbot.timer
sudo certbot renew --dry-run
curl --fail "https://$BLOG_DOMAIN/api/v1/health"
```

80 포트의 challenge 경로를 유지해야 webroot 방식 갱신이 가능합니다. 다른 HTTP 요청은 HTTPS로 이동하지만
앱은 리디렉션을 따라가지 않으므로 **처음부터 HTTPS URL**을 저장해야 합니다.
Nginx는 WebSocket Upgrade와 ZIP 업로드를 프록시하며 Uvicorn은 127.0.0.1의 전달 헤더만 신뢰합니다.

## 4. Windows에서 실제 연결 확인

```powershell
curl.exe --fail https://blog.example.com/api/v1/health
```

`{"status":"ok"}`를 확인한 뒤 앱의 서버 URL에 `https://blog.example.com`, 토큰에 서버의
`BLOG_DEVICE_TOKEN`을 저장하고 **연결 / 이벤트 조회**를 실행합니다. 이어 Mock 이벤트 전송,
패키지 업로드, Android 페어링·다운로드·실시간 알림을 확인합니다.
health 성공만으로 토큰 인증까지 검증된 것은 아닙니다.

| 증상 | 확인할 항목 |
|---|---|
| 원격 HTTP 주소 거부 | Nginx TLS를 설치하고 HTTPS 도메인 사용 |
| `WRONG_VERSION_NUMBER` | `https://...:8000` 대신 Nginx의 HTTPS 443 사용 |
| 인증서 검증 실패 | 도메인 일치, 만료, fullchain.pem, PC 시간 확인 |
| 연결 실패/시간 초과 | DNS, 443 방화벽, Nginx 서비스 확인 |
| 502/504 | ai-blog 서비스 및 proxy_pass의 127.0.0.1:8000 확인 |
| 401 | Windows 토큰과 서버 환경파일의 토큰 비교 |
| 404 | URL의 /api/v1 제거, 올바른 Nginx 사이트가 로드됐는지 확인 |

## 도메인 없이 Windows에서 개발 시험

Windows 터미널에서 SSH 연결을 유지합니다. 로컬 포트 18000이 사용 중이면 다른 포트를 선택합니다.

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18000:127.0.0.1:8000 사용자@우분투서버
```

앱 주소는 `http://127.0.0.1:18000`입니다. 원격 구간은 SSH로 암호화됩니다.
이 터널은 Windows 개발용이며 Android 운영 연결에는 HTTPS 구성을 사용합니다.

공식 참고: [Ubuntu 인증서 발급](https://ubuntu.com/server/docs/how-to/security/obtain-tls-certificates/),
[Certbot](https://certbot.eff.org/instructions?os=ubuntufocal&tab=standard&ws=other),
[Nginx WebSocket 프록시](https://nginx.org/en/docs/http/websocket.html).
