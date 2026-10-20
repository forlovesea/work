# 현장 설치 버전관리 (Installed Management Version)

스마트폰 브라우저에서 현장 방문 날짜, 장치별 설치/업그레이드 버전, 축전지 랙별 모듈 수를 기록하는 독립형 PHP + SQLite 웹앱입니다. Composer 패키지 없이 Apache의 PHP 핸들러와 PDO SQLite 확장으로 실행합니다.
앱을 열 때 암호 로그인이 필요하며, 모든 데이터 API도 로그인 세션을 확인합니다.

## 기능

- 현장방문날짜, 장치명, 기존 설치 버전, 업그레이드 버전 입력
- 기본 장치 `Door LCD`, `SMU02C` 제공 및 새 장치 추가
- 랙 수(1~100개)에 따라 랙별 모듈 수(1~10대) 선택
- `설치 정보 입력` / `설치 정보 조회` / `작업이력` 메뉴 분리
- 기본 암호 로그인 및 서버 측 암호 해시 저장, CLI 암호 변경
- 최근 1년간 설치 정보 등록·수정·삭제 이력과 작업 날짜/시간 확인
- 날짜 하루/기간(시작~끝)/전체 조회와 장비명 및 현재 설치 버전 필터
- 조회 결과의 기록 선택 삭제, 현재 필터 결과 전체 삭제 및 설치 정보 수정
- 이전 설치 기록을 선택해 장치, 버전, 랙과 모듈 구성을 자동 입력
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

앱은 TLS 인증서가 발급된 도메인의 `https://<실제-도메인>/installed-management/` 주소로 연결합니다. HTTPS에는 도메인에 유효한 TLS 인증서가 필요합니다. 기존 OpenProject의 `/OpenProject/` 프록시 규칙과 서비스를 변경하지 않고, OpenProject 설정이 이미 포함하도록 구성된 별도 `custom/server` 파일에 앱 전용 HTTPS 가상호스트를 추가합니다. 앱 경로는 HTTPS에서만 열고, Apache에서 모든 클라이언트 IP를 허용합니다. 앱 자체 암호 로그인은 계속 적용됩니다.

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

### 4. 도메인과 TLS 인증서 준비

Apache의 443 포트가 LISTEN 상태라는 것만으로 HTTPS 사이트와 인증서가 준비된 것은 아닙니다. 먼저 현재 가상호스트와 서버 이름을 확인합니다.

```bash
sudo apache2ctl -S
sudo grep -R -nE 'VirtualHost.*:443|ServerName|SSLCertificateFile|SSLCertificateKeyFile' \
  /etc/apache2/sites-enabled /etc/openproject/addons/apache2/includes \
  /etc/openproject/addons/apache2/custom
```

앞서 확인된 서버는 이미 TCP 443을 LISTEN하고 있으므로 `Listen 443`을 중복해서 추가하지 않습니다. `apache2ctl -S`에 기존 `*:443` 가상호스트가 표시되지 않고 아래 사용자 include 경로가 존재하면, 다음 단계처럼 앱 전용 가상호스트를 별도로 추가할 수 있습니다.

스마트폰에서 사용할 도메인(예: `installed.example.com`)을 준비하고, 해당 이름이 이 서버로 연결되도록 DNS를 설정합니다. 도메인에 유효한 인증서와 개인 키가 필요합니다. 아래 설정 예시는 인증서가 `/etc/letsencrypt/live/<실제-도메인>/`에 있다고 가정합니다. 이미 사용 중인 인증서가 있으면 실제 파일 경로를 사용하세요. 인증서가 없으면 서버 운영 정책에 맞는 절차로 먼저 발급하고, 발급 기관의 검증이 끝날 때까지 Apache 설정을 적용하지 마세요. 공개 CA 인증서는 일반적으로 도메인이 필요하며, 서버 IP만으로 접속하면 인증서 이름 검증이 맞지 않을 수 있습니다.

이미 같은 도메인을 처리하는 `*:443` 가상호스트가 있다면 중복 가상호스트를 만들지 말고, 해당 HTTPS 가상호스트 안에 아래 `Alias` 및 `<Directory>` 블록을 추가합니다. 같은 도메인에 새 HTTPS 가상호스트를 만드는 경우 기존 사이트 선택이 달라질 수 있으므로 설정 전에 운영자와 확인하세요.

### 5. 앱 전용 HTTPS 가상호스트 설정

현재 `/etc/apache2/sites-enabled/openproject.conf`는 다음 전역 사용자 설정 경로를 포함합니다.

```apache
IncludeOptional /etc/openproject/addons/apache2/custom/server/*.conf
```

아래 앱 전용 설정 파일을 만듭니다. 실제 도메인과 인증서 경로의 `<실제-도메인>`을 모두 교체하세요.

```bash
sudo install -d -o root -g root -m 755 /etc/openproject/addons/apache2/custom/server
sudo nano /etc/openproject/addons/apache2/custom/server/installed-management-https.conf
```

파일 내용:

```apache
<VirtualHost *:443>
    ServerName <실제-도메인>
    DocumentRoot /var/www/html

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/<실제-도메인>/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/<실제-도메인>/privkey.pem
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

먼저 Apache 설정 문법과 인증서 파일을 확인합니다. 도메인 자리표시자가 남아 있거나 인증서 경로가 실제 파일과 다르면 진행하지 마세요.

```bash
DOMAIN=installed.example.com
sudo test -s "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
sudo test -s "/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
sudo apache2ctl configtest
```

`AH01574: module dav_module is already loaded` 또는 `AH00558: apache2: Could not reliably determine the server's fully qualified domain name` 경고만 표시되더라도 마지막에 `Syntax OK`가 나오면 문법 검사는 통과한 것입니다. 이 앱을 연결하기 위해 기존 DAV 설정이나 전역 `ServerName`을 변경하지 마세요. `Syntax OK`가 나오지 않으면 reload하지 말고 오류를 해결합니다.

문법 검사가 통과하면 Apache를 중단하지 않는 graceful reload를 실행하고 상태를 확인합니다.

```bash
sudo systemctl reload apache2
sudo systemctl --no-pager --full status apache2
```

도메인의 DNS가 서버 IP를 가리키고, 네트워크 방화벽에서 TCP 443이 허용되어 있는지 확인합니다. 스마트폰 브라우저에서 `https://<실제-도메인>/installed-management/`를 열고 인증서 경고가 없는지 확인합니다. 기본 암호 `jjh1234`로 로그인한 뒤 바로 암호 변경 명령을 실행하세요. 화면과 설치 정보 조회를 확인하고 테스트 기록을 저장한 뒤 `data/installed-management.sqlite`가 생성되는지 확인합니다. `http://<서버-IP>:9230/installed-management/`는 더 이상 앱 접속 주소로 사용하지 않습니다.

### 로그인 암호 변경

기본 암호는 `jjh1234`입니다. 서버에서 아래 명령을 실행하면 새 암호를 두 번 입력하도록 안내하며 입력 중 암호는 화면에 표시되지 않습니다. 새 암호는 8~72바이트여야 합니다.

```bash
sudo php /home/jihyun/proj/github/work/InstalledManagementVersion/bin/set-password.php
```

암호 해시는 `data/password.hash`에 해시 형태로 저장되며 웹 공개 디렉터리 밖에 있고 Git에도 포함되지 않습니다. Apache의 `www-data` 계정이 읽을 수 있도록 명령은 `sudo`로 실행해야 합니다. 암호 변경 후 Apache 재시작은 필요하지 않습니다. 다른 계정에 설치한 경우 명령 경로의 `/home/jihyun`을 실제 경로로 바꾸세요.

HTTPS 인증서가 만료되거나 도메인과 일치하지 않으면 로그인하지 말고 인증서/갱신 설정을 먼저 확인합니다. HTTPS 연결에서 앱은 PHP 세션 쿠키에 `Secure`, `HttpOnly`, `SameSite=Strict` 속성을 설정합니다. HTTPS로 암호화하더라도 서버와 애플리케이션을 최신 상태로 유지하고, 관리자 암호를 강하게 설정하세요. `Require all granted`를 사용하므로 네트워크 방화벽에서 필요한 포트만 허용하고 서버 관리 인터페이스는 외부에 노출하지 않는 것이 좋습니다.

서버에서 로그를 확인하려면 다음을 사용합니다.

```bash
sudo tail -n 80 /var/log/apache2/error.log
sudo tail -n 80 /var/log/apache2/access.log
```

문제가 생기면 `/etc/openproject/addons/apache2/custom/server/installed-management-https.conf` 파일을 확인하거나 비활성화하고, `sudo apache2ctl configtest`가 `Syntax OK`인지 확인한 뒤 `sudo systemctl reload apache2`를 실행합니다. OpenProject의 `openproject.conf`와 기존 서비스 설정은 수정하지 않습니다. PHP-FPM 또는 SQLite 오류는 Apache 오류 로그와 `sudo systemctl status php7.4-fpm`에서 확인합니다.

업그레이드 버전 입력란은 Door LCD 요청에 맞춰 `v0.0.0.9`로 미리 채워져 있으며, 다른 장치의 버전을 입력할 때 수정할 수 있습니다.

조회 메뉴의 `현재 설치된 버전`은 각 방문 기록의 `업그레이드 버전`을 기준으로 검색합니다. 조회 조건은 날짜 범위, 장치명, 현재 설치 버전을 조합할 수 있습니다. 입력 메뉴의 `이전 입력 불러오기`는 최근 100개 기록에서 항목을 선택하며, 이전 방문 날짜 대신 오늘 날짜를 채워 새 현장 입력을 준비합니다.

## 설치 기록 수정 및 삭제

조회 목록에서 각 기록의 `수정`을 누르면 입력 화면에 해당 기록의 값이 채워집니다. 내용을 고친 다음 `수정 내용 저장`을 누르면 반영되며, `수정 취소`를 누르면 변경을 저장하지 않고 입력 모드를 종료합니다.

기록 왼쪽의 체크박스로 삭제할 항목을 고른 뒤 `선택 삭제`를 누르세요. `현재 목록 전체 선택`은 현재 화면에 조회된 기록만 선택합니다. `현재 조회 결과 전체 삭제`는 날짜·장비명·현재 설치 버전 필터에 맞는 기록만 삭제하며, 다른 조회 조건의 기록은 삭제하지 않습니다. 두 삭제 작업 모두 확인 창을 표시합니다. 삭제한 기록은 복구할 수 없으므로 확인 전에 건수와 조회 조건을 확인하세요.

## Excel로 여러 현장 일괄 등록

입력 메뉴의 `Excel 템플릿` 버튼으로 `.xlsx` 템플릿을 내려받아 작성하면 현장 기록 여러 개를 한 번에 등록할 수 있습니다. 템플릿에는 `설치 정보` 입력 시트와 작성 방법을 안내하는 `작성 안내` 시트가 있습니다.

`설치 정보` 시트의 첫 행 제목은 수정하지 말고, 두 번째 행부터 **현장 하나를 한 행에** 입력합니다.

| 열 제목 | 입력 형식 |
| --- | --- |
| 현장방문날짜 | `YYYY-MM-DD` (예: `2026-10-20`) |
| 장비명 | `Door LCD`, `SMU02C` 또는 새 장비명 |
| 기존 설치 버전 | 버전 문자열 (예: `v0.0.0.8`) |
| 업그레이드 버전 | 버전 문자열 (예: `v0.0.0.9`) |
| 축전지 랙 수 | 1~100 사이의 정수 |
| 랙별 모듈 수 (쉼표 구분) | 랙 순서대로 1~10 사이의 모듈 수를 쉼표로 구분 (예: 랙 수가 3이면 `4,5,3`) |

완전히 빈 행은 건너뜁니다. 한 번에 최대 100개 현장을 업로드할 수 있으며, 파일 크기는 최대 5MB입니다. `.xls` 파일은 지원하지 않습니다. 작성한 `.xlsx` 파일을 선택하면 앱이 각 행을 검증하고 미리보기와 오류 행을 표시합니다. 오류가 있으면 일괄 등록 버튼이 비활성화되므로 Excel에서 오류를 수정한 뒤 파일을 다시 선택하세요. 등록 시 서버에서도 모든 행을 다시 검사하고, 전체 행이 유효할 때만 한 번의 데이터베이스 트랜잭션으로 저장합니다. 따라서 한 행이라도 잘못되면 일부 현장만 저장되는 일은 없습니다.

스프레드시트는 브라우저 안에서 처리되며 별도 앱 설치나 외부 라이브러리 연결이 필요하지 않습니다. 업로드 압축 해제를 지원하지 않는 구형 브라우저에서는 최신 모바일 Chrome, Edge 또는 Safari로 다시 시도하세요.

## 조회 결과 내보내기

조회 메뉴 하단에서 CSV, Excel 통합 문서(`.xlsx`), PDF 형식을 선택할 수 있습니다. 내보내기에는 화면에 표시된 것과 동일한 필터 결과만 포함됩니다. CSV는 한글 인코딩을 위한 UTF-8 BOM을 포함하고, Excel 파일은 외부 패키지나 CDN 없이 브라우저에서 생성합니다.

PDF 선택 시 브라우저 인쇄 창이 열립니다. 인쇄 대상에서 `PDF로 저장`을 선택하면 PDF를 저장할 수 있으며, 같은 조회 결과의 CSV도 함께 다운로드됩니다. `보고서 형식`을 체크하면 문서 제목, 적용한 조회 조건, 기록/장비/랙/모듈 합계, 버전 변경 요약, 현장별 상세 표와 참고 사항을 갖춘 고객 전달용 보고서를 인쇄합니다. 체크하지 않으면 조회 조건과 결과 표 중심의 간단한 PDF가 만들어집니다. PDF 저장 메뉴 표시는 브라우저와 기기별로 다를 수 있습니다.

## 데이터 위치와 백업

기록은 `data/installed-management.sqlite`에, 로그인 암호 해시는 `data/password.hash`에 저장됩니다. 둘 다 웹 공개 디렉터리(`public`) 밖에 있으므로 웹에서 직접 접근할 수 없습니다. 브라우저와 서버 사이의 로그인 및 데이터 전송은 HTTPS를 사용하세요. 백업 시 SQLite 파일을 복사하고, 일관된 백업이 필요하면 SQLite 백업 도구 또는 서비스 점검 시간을 이용하세요. `data` 디렉터리를 공개 저장소에 커밋하지 마세요.

`작업이력`에는 설치 정보의 등록, 수정, 삭제 작업이 서버의 UTC 시각 기준으로 기록되며 화면에는 한국 시간(Asia/Seoul)으로 표시됩니다. 수정 이력에는 변경된 항목과 변경 전·후 값이 함께 표시됩니다. 최근 1년의 이력만 보관하고, 앱이 실행될 때 1년보다 오래된 이력은 자동으로 정리합니다. 등록 또는 수정/삭제와 이력 저장은 같은 데이터베이스 트랜잭션에서 처리됩니다. 작업이력 기능을 적용하기 전에 저장되어 있던 기록에는 과거 작업 이력이 없으므로, 기능 적용 이후의 작업부터 기록됩니다.
