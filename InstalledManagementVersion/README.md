# 현장 설치 버전관리 (Installed Management Version)

스마트폰 브라우저에서 현장 방문 날짜, 장치별 설치/업그레이드 버전, 축전지 Rack별 모듈 수를 기록하는 독립형 PHP + SQLite 웹앱입니다. Composer 패키지 없이 Apache의 PHP 핸들러와 PDO SQLite 확장으로 실행합니다.
앱을 열 때 암호 로그인이 필요하며, 모든 데이터 API도 로그인 세션을 확인합니다.

## 기능

- 축전지 Rack 이름은 `Rack 01`, `Rack 02` 등을 기본값으로 사용하며 직접 수정 가능 (100자 이내, 빈 이름은 기본값 적용)
- 저장한 Rack 이름은 수정·이전 입력 불러오기·조회·작업이력·내보내기에 반영되며 기존 기록은 기본 이름으로 표시

- 설치장소(국소), 주소, 담당자 이름·연락처 입력 및 담당자 `+추가`/삭제 (최대 20명)
- 설치 특이사항을 여러 줄로 기록하는 비고와 작업상태(방문예정/작업완료/작업실패/작업보류/기타) 입력
- 작업상태가 기타인 경우 상세 상태 필수 입력, 새 항목의 저장·수정·불러오기·조회 및 CSV/Excel/PDF 내보내기
- 기존 SQLite 데이터베이스는 최초 API 호출 시 새 열을 자동 추가하며, 기존 기록의 작업상태 기본값은 방문예정

- 현장방문날짜, 장치명, 기존 설치 버전, 업그레이드 버전 입력
- 기본 장치 `SMU02C + Door LCD`, `Door LCD`, `iIoT Gateway`(세 번째), `SMU02C` 순서로 제공 및 새 장치 추가
- Rack 수(1~100개)에 따라 Rack별 모듈 수(1~10대) 선택
- `설치 정보 입력` / `설치 정보 조회` / `작업이력` 메뉴 분리
- 기본 암호 로그인 및 서버 측 암호 해시 저장, CLI 암호 변경
- 최근 1년간 설치 정보 등록·수정·삭제 이력과 작업 날짜/시간 확인
- 날짜 하루/기간(시작~끝)/전체 조회와 장비명 및 현재 설치 버전 필터
- 조회 결과의 기록 선택 삭제, 현재 필터 결과 전체 삭제 및 설치 정보 수정
- 이전 설치 기록을 선택해 장치, 버전, Rack과 모듈 구성을 자동 입력
- 기존/업그레이드 버전 입력란에서 저장된 버전을 자동완성으로 선택
- Excel 템플릿 다운로드, 여러 현장 정보 검증 및 일괄 등록
- 현재 조회 결과를 CSV, Excel 통합 문서(.xlsx), PDF로 내보내기
- PDF 보고서 형식 선택 시 고객 전달용 요약·상세 내역과 CSV 동시 다운로드
- 저장한 현장 기록과 장치 목록을 SQLite로 공유
- 모바일 화면에 맞춘 반응형 UI

## 요구사항

- Ubuntu 20.04.6
- Apache 2.4 및 Apache에서 실행 가능한 PHP 7.4 이상
- PHP PDO SQLite 확장 (`pdo_sqlite`)

앱은 `https://61.105.141.21/installed-management/` 주소로 연결합니다. HTTPS를 사용하려면 인증서에 공인 IP `61.105.141.21`이 IP 주소 SAN(Subject Alternative Name)으로 포함되어 있어야 하며, 스마트폰이 신뢰하는 인증기관(CA)이 발급한 인증서를 사용해야 합니다. 기존 OpenProject의 `/OpenProject/` 프록시 규칙과 서비스를 변경하지 않고, OpenProject 설정이 이미 포함하도록 구성된 별도 `custom/server` 파일에 앱 전용 HTTPS 가상호스트를 추가합니다. 앱 경로는 HTTPS에서만 열고, Apache에서 모든 클라이언트 IP를 허용합니다. 앱 자체 암호 로그인은 계속 적용됩니다.

## 설치 및 Apache 연결 예시

### 1. GitHub에서 프로젝트 내려받기

Ubuntu 서버에 접속한 뒤 Git이 있는지 확인합니다.

```bash
git --version
```

Git이 없다면 서버 관리자가 설치합니다.

```bash
sudo apt update
sudo apt install git
```

아래 명령은 이미 사용 중인 계정 `jihyun`의 `/home/jihyun/proj/github/work/InstalledManagementVersion` 경로를 기준으로 합니다. 다른 계정이라면 `/home/jihyun`을 실제 홈 경로로 바꾸세요. 저장소 루트 `/home/jihyun/proj/github/work`가 아직 없는 새 설치라면 아래 명령으로 내려받습니다.

```bash
mkdir -p /home/jihyun/proj/github
git clone --depth 1 --filter=blob:none --sparse --branch main \
  https://github.com/forlovesea/work.git \
  /home/jihyun/proj/github/work
git -C /home/jihyun/proj/github/work \
  sparse-checkout set InstalledManagementVersion
```

저장소가 이미 내려받아져 있다면 위 `git clone`은 다시 실행하지 말고 다음처럼 최신 코드를 가져옵니다.

```bash
git -C /home/jihyun/proj/github/work pull --ff-only origin main
```

웹 파일은 저장소의 `public` 디렉터리에서 직접 서비스합니다. Apache의 `www-data` 계정은 홈 경로를 통과하고 `public`을 읽어야 하며, SQLite의 `data` 디렉터리에는 쓸 수 있어야 합니다. 다른 개인 파일은 읽지 못하도록 ACL로 최소 권한을 부여합니다.

```bash
sudo apt install acl
sudo setfacl -m u:www-data:--x /home/jihyun
sudo setfacl -m u:www-data:--x /home/jihyun/proj
sudo setfacl -m u:www-data:--x /home/jihyun/proj/github
sudo setfacl -m u:www-data:--x /home/jihyun/proj/github/work
sudo setfacl -m u:www-data:rx /home/jihyun/proj/github/work/InstalledManagementVersion
sudo setfacl -m u:www-data:rwx \
  /home/jihyun/proj/github/work/InstalledManagementVersion/data
sudo setfacl -m d:u:www-data:rwx \
  /home/jihyun/proj/github/work/InstalledManagementVersion/data
```

다음 명령으로 ACL을 확인합니다. `www-data`가 `public` 파일을 읽고 `data`에 파일을 만들 수 있는지 확인하되, 홈 디렉터리를 목록으로 읽을 권한(`r`)은 주지 않습니다.

```bash
getfacl /home/jihyun /home/jihyun/proj/github/work/InstalledManagementVersion/public
getfacl /home/jihyun/proj/github/work/InstalledManagementVersion/data
```

Apache 공개 경로는 `/home/jihyun/proj/github/work/InstalledManagementVersion/public`, SQLite 파일 경로는 `/home/jihyun/proj/github/work/InstalledManagementVersion/data/installed-management.sqlite`입니다.

### 2. 이후 최신 버전으로 갱신

최초 clone을 수행한 Linux 사용자 계정으로 GitHub의 `main` 브랜치를 fast-forward 갱신합니다. 저장소 위치에서 공개 파일을 직접 서비스하므로 별도의 파일 복사는 필요하지 않습니다.

```bash
git -C /home/jihyun/proj/github/work pull --ff-only origin main
```

이 갱신 절차는 추적되지 않는 `data/installed-management.sqlite` 파일을 덮어쓰거나 삭제하지 않습니다. 배포 전 데이터베이스를 백업하고, 갱신 후 앱을 확인하세요.

### 3. PHP-FPM과 SQLite 확장 설치

현재 확인한 서버에는 PHP CLI와 Apache PHP 핸들러가 없고, Apache는 `mpm_event`를 사용합니다. 기존 OpenProject 가상호스트에 앱을 추가하기 위해 PHP 7.4 FPM을 설치합니다. 이 작업은 기존 OpenProject `ProxyPass`를 변경하지 않습니다.

```bash
sudo apt update
sudo apt install php7.4-cli php7.4-fpm php7.4-sqlite3
sudo a2enmod ssl proxy_fcgi setenvif
sudo systemctl enable --now php7.4-fpm
sudo systemctl --no-pager --full status php7.4-fpm
ls -l /run/php/php7.4-fpm.sock
```

SQLite PDO 확장이 CLI와 FPM에 설치됐는지 확인합니다.

```bash
php -m | grep -Ei 'PDO|pdo_sqlite'
php-fpm7.4 -i | grep -i pdo_sqlite
```

두 명령에서 `pdo_sqlite`가 모두 확인되지 않으면 다음 단계로 진행하지 말고 패키지 설치 오류를 해결합니다. `php -v`가 처음에 “명령을 찾을 수 없음”이었던 것은 CLI 미설치 상태이므로 `php7.4-cli`도 명시적으로 설치합니다.

### 4. 공인 IP용 TLS 인증서 준비

Apache의 443 포트가 LISTEN 상태라는 것만으로 IP 주소용 인증서가 설치되어 있거나 HTTPS가 준비된 것은 아닙니다. 먼저 현재 가상호스트와 인증서 설정을 확인합니다.

```bash
sudo apache2ctl -S
sudo grep -R -nE 'VirtualHost.*:443|ServerName|SSLCertificateFile|SSLCertificateKeyFile' \
  /etc/apache2/sites-enabled /etc/openproject/addons/apache2/includes \
  /etc/openproject/addons/apache2/custom
```

앞서 확인된 서버는 이미 TCP 443을 LISTEN하고 있으므로 `Listen 443`을 중복해서 추가하지 않습니다. `apache2ctl -S`에 기존 `*:443` 가상호스트가 표시되지 않고 아래 사용자 include 경로가 존재하면, 다음 단계처럼 앱 전용 가상호스트를 별도로 추가할 수 있습니다.

도메인이나 DNS 레코드는 사용하지 않습니다. 인증서 발급 기관에 `61.105.141.21` IP 주소 자체가 인증서 SAN에 들어가는 인증서를 요청하세요. **도메인 이름만 들어 있는 인증서는 이 IP 주소 접속에 사용할 수 없습니다.** 발급 기관이 공인 IP용 인증서를 제공하는지, 이 IP를 검증할 수 있는지, 갱신 주기와 자동 갱신 방법이 무엇인지 사전에 확인하세요. 인증서가 준비되기 전에는 HTTPS 설정을 적용하지 않습니다.

이 서버에서 확인한 `remotecontrol-ip` 인증서를 재사용할 수 있습니다. 인증서와 짝이 확인된 개인 키는 다음 경로입니다. 파일을 복사하거나 권한을 완화하지 말고 Apache 설정에서 이 경로를 직접 참조합니다.

```bash
sudo openssl x509 -in /etc/letsencrypt/live/remotecontrol-ip/fullchain.pem \
  -noout -ext subjectAltName
sudo test -s /etc/letsencrypt/live/remotecontrol-ip/privkey.pem
```

출력에 `IP Address:61.105.141.21`이 있어야 합니다. 인증서가 이 IP를 포함하지 않거나 스마트폰에서 신뢰되지 않으면 경고를 무시하거나 브라우저 보안을 낮추지 마세요. 자체 서명 인증서를 사용할 경우에는 모든 스마트폰에 해당 인증서를 신뢰하도록 별도로 설치·관리해야 하며, 그 전까지는 정상적인 공개 HTTPS로 사용할 수 없습니다.

인증서 확인 시 만료일이 2026년 10월 26일로 확인되었으며 단기 인증서입니다. Certbot의 `snap.certbot.renew.timer`가 자동 갱신을 예약하고, 다음 명령의 dry-run이 성공하는지 확인했습니다. 갱신 후 Apache도 새 인증서를 읽도록 아래 별도 deploy hook을 설정하세요.

```bash
sudo systemctl list-timers --all | grep -i certbot
sudo certbot renew --cert-name remotecontrol-ip --dry-run
```

`*:443` 기존 HTTPS 가상호스트가 있으면 중복 가상호스트를 만들지 말고, 해당 HTTPS 가상호스트에 앱 `Alias` 및 `<Directory>` 블록을 추가합니다. 기존 443 기본 가상호스트가 OpenProject 또는 다른 서비스를 처리한다면 새 가상호스트가 그 서비스의 HTTPS 응답을 바꾸지 않는지 운영자와 확인하세요.

### 5. 앱 전용 HTTPS 가상호스트 설정

현재 `/etc/apache2/sites-enabled/openproject.conf`는 다음 전역 사용자 설정 경로를 포함합니다.

```apache
IncludeOptional /etc/openproject/addons/apache2/custom/server/*.conf
```

아래 앱 전용 설정 파일을 만듭니다. 인증서 경로가 실제 인증서 및 개인 키 파일과 일치하는지 확인하세요.

```bash
sudo install -d -o root -g root -m 755 /etc/openproject/addons/apache2/custom/server
sudo nano /etc/openproject/addons/apache2/custom/server/installed-management-https.conf
```

파일 내용:

```apache
<VirtualHost *:443>
    ServerName 61.105.141.21
    DocumentRoot /var/www/html

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/remotecontrol-ip/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/remotecontrol-ip/privkey.pem
    SetEnv HTTPS on

    Alias /installed-management /home/jihyun/proj/github/work/InstalledManagementVersion/public

    <Directory /home/jihyun/proj/github/work/InstalledManagementVersion/public>
        DirectoryIndex index.php
        Options -Indexes
        AllowOverride None
        Require all granted

        <FilesMatch "\.php$">
            SetHandler "proxy:unix:/run/php/php7.4-fpm.sock|fcgi://localhost"
        </FilesMatch>
    </Directory>
</VirtualHost>
```

`Require all granted`는 HTTPS 가상호스트에서 모든 클라이언트 IP의 접속을 허용합니다. 인증서가 정상인 HTTPS 주소에서만 앱 경로가 제공되도록 이 `Alias`를 기존 HTTP `*:9230` 가상호스트에 추가하지 마세요. 이전에 HTTP `*:9230`에 앱 Alias를 설정했다면 다음처럼 해당 앱 전용 설정 파일만 비활성화합니다. 다른 OpenProject 설정 파일은 변경하지 않습니다.

```bash
sudo mv /etc/openproject/addons/apache2/custom/vhost/installed-management.conf \
  /etc/openproject/addons/apache2/custom/vhost/installed-management.conf.disabled
```

현재 Apache의 다른 `*:443` 가상호스트와 인증서를 덮어쓰지 않습니다. 기존 HTTPS 가상호스트를 재사용하는 경우 `SSLEngine` 및 인증서 지시어는 그 가상호스트에 이미 설정된 값을 유지하고, 앱 Alias/Directory만 추가하세요.

### 6. 문법 검사 후 안전하게 반영

먼저 인증서 SAN과 인증서/개인 키 파일, Apache 설정 문법을 확인합니다. IP SAN이 없거나 파일 경로가 실제 파일과 다르면 진행하지 마세요.

```bash
sudo openssl x509 -in /etc/letsencrypt/live/remotecontrol-ip/fullchain.pem \
  -noout -ext subjectAltName
sudo test -s /etc/letsencrypt/live/remotecontrol-ip/fullchain.pem
sudo test -s /etc/letsencrypt/live/remotecontrol-ip/privkey.pem
sudo apache2ctl configtest
```

인증서 출력에 `IP Address:61.105.141.21`이 있는지 확인한 뒤 진행합니다.

`AH01574: module dav_module is already loaded` 또는 `AH00558: apache2: Could not reliably determine the server's fully qualified domain name` 경고만 표시되더라도 마지막에 `Syntax OK`가 나오면 문법 검사는 통과한 것입니다. 이 앱을 연결하기 위해 기존 DAV 설정이나 전역 `ServerName`을 변경하지 마세요. `Syntax OK`가 나오지 않으면 reload하지 말고 오류를 해결합니다.

문법 검사가 통과하면 Apache를 중단하지 않는 graceful reload를 실행하고 상태를 확인합니다.

```bash
sudo systemctl reload apache2
sudo systemctl --no-pager --full status apache2
```

### 7. Certbot 갱신 후 Apache 자동 reload 설정

Certbot의 `remotecontrol.sh` deploy hook은 `remotecontrol-ip` 인증서를 `/etc/remotecontrol/`에 복사하고 `remotecontrol-relay.service`를 재시작하지만, Apache는 reload하지 않습니다. 기존 hook은 수정하지 말고 Apache 전용 hook을 별도 파일로 추가합니다. 이 hook은 `remotecontrol-ip` 인증서가 실제 갱신되었을 때만 실행됩니다.

```bash
sudo nano /etc/letsencrypt/renewal-hooks/deploy/installed-management-apache.sh
```

아래 내용을 저장합니다.

```sh
#!/bin/sh
set -eu

[ "${RENEWED_LINEAGE:-}" = "/etc/letsencrypt/live/remotecontrol-ip" ] || exit 0

/usr/sbin/apache2ctl configtest
/usr/bin/systemctl reload apache2
```

파일을 root 소유로 설정하고 실행 권한을 부여한 뒤 스크립트 문법을 확인합니다.

```bash
sudo chown root:root /etc/letsencrypt/renewal-hooks/deploy/installed-management-apache.sh
sudo chmod 750 /etc/letsencrypt/renewal-hooks/deploy/installed-management-apache.sh
sudo sh -n /etc/letsencrypt/renewal-hooks/deploy/installed-management-apache.sh
```

이 hook은 Apache 설정이 유효할 때만 reload합니다. Apache HTTPS 가상호스트를 먼저 설치하고 `sudo apache2ctl configtest`가 `Syntax OK`인지 확인한 다음 hook을 활성화하세요. 기존 `remotecontrol.sh`, Nginx hook, Certbot timer는 수정하지 않습니다. Certbot dry-run은 시험 인증서 갱신이므로 deploy hook이 실행되지 않을 수 있습니다. 실제 갱신을 기다리지 않고 hook을 확인하려고 수동 실행하면 Apache를 reload하게 되므로, 먼저 설정 검사와 앱 접속을 확인하세요.

네트워크 방화벽에서 TCP 443이 허용되어 있는지 확인합니다. 스마트폰 브라우저에서 `https://61.105.141.21/installed-management/`를 열고 인증서 경고가 없는지 확인합니다. 기본 암호 `jjh1234`로 로그인한 뒤 바로 암호 변경 명령을 실행하세요. 화면과 설치 정보 조회를 확인하고 테스트 기록을 저장한 뒤 `data/installed-management.sqlite`가 생성되는지 확인합니다. `http://61.105.141.21:9230/installed-management/`는 더 이상 앱 접속 주소로 사용하지 않습니다.

### 로그인 암호 변경

기본 암호는 `jjh1234`입니다. 서버에서 아래 명령을 실행하면 새 암호를 두 번 입력하도록 안내하며 입력 중 암호는 화면에 표시되지 않습니다. 새 암호는 8~72바이트여야 합니다.

```bash
sudo php /home/jihyun/proj/github/work/InstalledManagementVersion/bin/set-password.php
```

암호 해시는 `data/password.hash`에 해시 형태로 저장되며 웹 공개 디렉터리 밖에 있고 Git에도 포함되지 않습니다. Apache의 `www-data` 계정이 읽을 수 있도록 명령은 `sudo`로 실행해야 합니다. 암호 변경 후 Apache 재시작은 필요하지 않습니다. 다른 계정에 설치한 경우 명령 경로의 `/home/jihyun`을 실제 경로로 바꾸세요.

HTTPS 인증서가 만료되거나 `61.105.141.21` IP SAN이 없거나 스마트폰에서 신뢰되지 않으면 로그인하지 말고 인증서/갱신 설정을 먼저 확인합니다. HTTPS 연결에서 앱은 PHP 세션 쿠키에 `Secure`, `HttpOnly`, `SameSite=Strict` 속성을 설정합니다. HTTPS로 암호화하더라도 서버와 애플리케이션을 최신 상태로 유지하고, 관리자 암호를 강하게 설정하세요. `Require all granted`를 사용하므로 네트워크 방화벽에서 필요한 포트만 허용하고 서버 관리 인터페이스는 외부에 노출하지 않는 것이 좋습니다.

서버에서 로그를 확인하려면 다음을 사용합니다.

```bash
sudo tail -n 80 /var/log/apache2/error.log
sudo tail -n 80 /var/log/apache2/access.log
```

문제가 생기면 `/etc/openproject/addons/apache2/custom/server/installed-management-https.conf` 파일을 확인하거나 비활성화하고, `sudo apache2ctl configtest`가 `Syntax OK`인지 확인한 뒤 `sudo systemctl reload apache2`를 실행합니다. OpenProject의 `openproject.conf`와 기존 서비스 설정은 수정하지 않습니다. PHP-FPM 또는 SQLite 오류는 Apache 오류 로그와 `sudo systemctl status php7.4-fpm`에서 확인합니다.

모든 장비의 업그레이드 버전 입력란은 기본적으로 비어 있으며, 실제 업그레이드할 버전을 직접 입력합니다. 통합 장비의 Door LCD 업그레이드 버전도 빈칸으로 시작합니다. 저장된 기록을 수정하거나 불러올 때는 저장된 버전을 유지합니다.

상단 원형 차트는 전체 기간의 모든 등록 기록 중 `작업완료` 비율을 표시합니다. 나머지 작업상태는 미완료로 집계합니다. 장치별 누적 세로 막대는 작업완료·방문예정·작업보류·작업실패·기타 비율을 표시하며, 조회 필터와 무관하게 전체 현황을 유지합니다. 막대 아래 상세 표에서 모든 상태의 건수와 비율을 확인할 수 있습니다. 기록이 없는 장치는 ‘기록 없음’으로 표시하며, 기록 등록·수정·삭제 후 현황이 갱신됩니다.

입력 화면에서 SMU02C(통합 장비 포함)의 기존 설치 버전 기본값은 `V100R024C10SPC235`, iIoT Gateway는 `V100R024C10SPC265`입니다. 장치 선택 시 자동 입력되며 직접 수정할 수 있습니다. 저장된 기록을 수정하거나 불러올 때는 저장된 버전을 유지합니다.

조회 메뉴의 `현재 설치된 버전`은 각 방문 기록의 `업그레이드 버전`을 기준으로 검색합니다. 조회 조건은 날짜 범위, 장치명, 현재 설치 버전을 조합할 수 있습니다. 입력 메뉴의 `이전 입력 불러오기`는 최근 100개 기록에서 항목을 선택하며, 이전 방문 날짜 대신 오늘 날짜를 채워 새 현장 입력을 준비합니다.

## 설치 기록 수정 및 삭제

조회 목록에서 각 기록의 `수정`을 누르면 입력 화면에 해당 기록의 값이 채워집니다. 내용을 고친 다음 `수정 내용 저장`을 누르면 반영되며, `수정 취소`를 누르면 변경을 저장하지 않고 입력 모드를 종료합니다.

기록 왼쪽의 체크박스로 삭제할 항목을 고른 뒤 `선택 삭제`를 누르세요. `현재 목록 전체 선택`은 현재 화면에 조회된 기록만 선택합니다. `현재 조회 결과 전체 삭제`는 날짜·장비명·현재 설치 버전 필터에 맞는 기록만 삭제하며, 다른 조회 조건의 기록은 삭제하지 않습니다. 두 삭제 작업 모두 확인 창을 표시합니다. 삭제한 기록은 복구할 수 없으므로 확인 전에 건수와 조회 조건을 확인하세요.

## Excel로 여러 현장 일괄 등록

입력 메뉴의 `Excel 템플릿` 버튼으로 `.xlsx` 템플릿을 내려받아 작성하면 현장 기록 여러 개를 한 번에 등록할 수 있습니다. 템플릿에는 `설치 정보` 입력 시트와 작성 방법을 안내하는 `작성 안내` 시트가 있습니다.

`설치 정보` 시트의 첫 행 제목은 수정하지 말고, 두 번째 행부터 **현장 하나를 한 행에** 입력합니다.

| 열 제목 | 입력 형식 |
| --- | --- |
| 설치장소(국소) | 100자 이내 |
| 주소 | 300자 이내 |
| 작업상태 | 상태 목록에서 선택. 빈 상태는 방문예정 |
| 담당자 이름 | 100자 이내. 연락처와 함께 입력 |
| 담당자 연락처 | 50자 이내. 텍스트 형식으로 앞자리 0 유지 |
| 현장방문날짜 | `YYYY-MM-DD` (예: `2026-10-20`) |
| 장비명 | `SMU02C + Door LCD`, `Door LCD`, `iIoT Gateway`(세 번째), `SMU02C` 또는 새 장비명 |

새 템플릿은 위 7개 열만 제공합니다. 버전·Rack·비고는 등록 후 웹에서 수정합니다. 기본 양식 업로드 시 Rack 1개·모듈 10개를 설정하고 기존 버전은 SMU02C(통합 포함) `V100R024C10SPC235`, iIoT Gateway `V100R024C10SPC265`를 적용합니다. 다른 장비의 기존 버전과 모든 업그레이드 버전, 통합 장비의 Door LCD 버전은 빈칸으로 등록합니다. 기존 6열 및 이전 확장 템플릿 업로드도 계속 지원합니다.

완전히 빈 행과 기본값만 남은 미작성 행은 건너뜁니다. 한 번에 최대 100개 현장을 업로드할 수 있으며, 파일 크기는 최대 5MB입니다. `.xls` 파일은 지원하지 않습니다. 작성한 `.xlsx` 파일을 선택하면 앱이 각 행을 검증하고 미리보기와 오류 행을 표시합니다. 오류가 있으면 일괄 등록 버튼이 비활성화되므로 Excel에서 오류를 수정한 뒤 파일을 다시 선택하세요. 등록 시 서버에서도 모든 행을 다시 검사하고, 전체 행이 유효할 때만 한 번의 데이터베이스 트랜잭션으로 저장합니다. 따라서 한 행이라도 잘못되면 일부 현장만 저장되는 일은 없습니다.

스프레드시트는 브라우저 안에서 처리되며 별도 앱 설치나 외부 라이브러리 연결이 필요하지 않습니다. 업로드 압축 해제를 지원하지 않는 구형 브라우저에서는 최신 모바일 Chrome, Edge 또는 Safari로 다시 시도하세요.

## 조회 결과 내보내기

조회 메뉴 하단에서 CSV, Excel 통합 문서(`.xlsx`), PDF 형식을 선택할 수 있습니다. 내보내기에는 화면에 표시된 것과 동일한 필터 결과만 포함됩니다. CSV는 한글 인코딩을 위한 UTF-8 BOM을 포함하고, Excel 파일은 외부 패키지나 CDN 없이 브라우저에서 생성합니다.

PDF 선택 시 브라우저 인쇄 창이 열립니다. 인쇄 대상에서 `PDF로 저장`을 선택하면 PDF를 저장할 수 있으며, 같은 조회 결과의 CSV도 함께 다운로드됩니다. `보고서 형식`을 체크하면 문서 제목, 적용한 조회 조건, 기록/장비/Rack/모듈 합계, 버전 변경 요약, 현장별 상세 표와 참고 사항을 갖춘 고객 전달용 보고서를 인쇄합니다. 체크하지 않으면 조회 조건과 결과 표 중심의 간단한 PDF가 만들어집니다. PDF 저장 메뉴 표시는 브라우저와 기기별로 다를 수 있습니다.

## 데이터 위치와 백업

기록은 `data/installed-management.sqlite`에, 로그인 암호 해시는 `data/password.hash`에 저장됩니다. 둘 다 웹 공개 디렉터리(`public`) 밖에 있으므로 웹에서 직접 접근할 수 없습니다. 브라우저와 서버 사이의 로그인 및 데이터 전송은 HTTPS를 사용하세요. 백업 시 SQLite 파일을 복사하고, 일관된 백업이 필요하면 SQLite 백업 도구 또는 서비스 점검 시간을 이용하세요. `data` 디렉터리를 공개 저장소에 커밋하지 마세요.

`작업이력`에는 설치 정보의 등록, 수정, 삭제 작업이 서버의 UTC 시각 기준으로 기록되며 화면에는 한국 시간(Asia/Seoul)으로 표시됩니다. 수정 이력에는 변경된 항목과 변경 전·후 값이 함께 표시됩니다. 최근 1년의 이력만 보관하고, 앱이 실행될 때 1년보다 오래된 이력은 자동으로 정리합니다. 등록 또는 수정/삭제와 이력 저장은 같은 데이터베이스 트랜잭션에서 처리됩니다. 작업이력 기능을 적용하기 전에 저장되어 있던 기록에는 과거 작업 이력이 없으므로, 기능 적용 이후의 작업부터 기록됩니다.
