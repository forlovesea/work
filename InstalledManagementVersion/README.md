# 현장 설치 버전관리 (Installed Management Version)

스마트폰 브라우저에서 현장 방문 날짜, 장치별 설치/업그레이드 버전, 축전지 랙별 모듈 수를 기록하는 독립형 PHP + SQLite 웹앱입니다. Composer 패키지 없이 Apache의 PHP 핸들러와 PDO SQLite 확장으로 실행합니다.

## 기능

- 현장방문날짜, 장치명, 기존 설치 버전, 업그레이드 버전 입력
- 기본 장치 `Door LCD`, `SMU02C` 제공 및 새 장치 추가
- 랙 수(1~100개)에 따라 랙별 모듈 수(1~10대) 선택
- `설치 정보 입력` / `설치 정보 조회` 메뉴 분리
- 날짜 하루/기간(시작~끝)/전체 조회와 장비명 및 현재 설치 버전 필터
- 이전 설치 기록을 선택해 장치, 버전, 랙과 모듈 구성을 자동 입력
- 기존/업그레이드 버전 입력란에서 저장된 버전을 자동완성으로 선택
- 현재 조회 결과를 CSV, Excel 통합 문서(.xlsx), PDF로 내보내기
- PDF 보고서 형식 선택 시 고객 전달용 요약·상세 내역과 CSV 동시 다운로드
- 저장한 현장 기록과 장치 목록을 SQLite로 공유
- 모바일 화면에 맞춘 반응형 UI

## 요구사항

- Ubuntu 20.04.6
- Apache 2.4 및 Apache에서 실행 가능한 PHP 7.4 이상
- PHP PDO SQLite 확장 (`pdo_sqlite`)

앱은 `/installed-management/` 별도 URL 경로로 연결합니다. 기존 원격제어 서버와 축전지 감시 서버의 설정을 덮어쓰지 않도록 **현재 사용하는 HTTPS 가상호스트 파일 하나에만 Alias와 접근 규칙을 추가**합니다. 설정을 적용하기 전에 해당 파일을 백업하고 Apache 문법 검사에 통과한 뒤 graceful reload를 사용합니다.

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

아래 예시는 Linux 계정명이 `user`이고 프로젝트를 요청하신 `/home/user/proj/github/work/InstalledManagementVersion` 경로에 설치하는 경우입니다. 실제 계정명이 다르면 명령의 `/home/user`를 해당 계정의 홈 경로로 바꾸세요. Git 저장소 루트는 `/home/user/proj/github/work`이며, 이 경로는 아직 없어야 합니다. 저장소 전체 파일을 작업 트리에 펼치지 않고 `InstalledManagementVersion`만 sparse checkout으로 내려받습니다.

```bash
mkdir -p /home/user/proj/github
git clone --depth 1 --filter=blob:none --sparse --branch main \
  https://github.com/forlovesea/work.git \
  /home/user/proj/github/work
git -C /home/user/proj/github/work \
  sparse-checkout set InstalledManagementVersion
```

웹 파일은 저장소의 `public` 디렉터리에서 직접 서비스합니다. Apache가 사용자 홈 경로를 통과하고, 앱의 SQLite 데이터 디렉터리에만 쓸 수 있도록 ACL을 설정합니다. `setfacl` 명령이 없다면 `acl` 패키지를 먼저 설치합니다.

```bash
sudo apt install acl
sudo setfacl -m u:www-data:--x /home/user
sudo setfacl -m u:www-data:--x /home/user/proj
sudo setfacl -m u:www-data:--x /home/user/proj/github
sudo setfacl -m u:www-data:--x /home/user/proj/github/work
sudo setfacl -m u:www-data:rx /home/user/proj/github/work/InstalledManagementVersion
sudo setfacl -m u:www-data:rwx \
  /home/user/proj/github/work/InstalledManagementVersion/data
sudo setfacl -m d:u:www-data:rwx \
  /home/user/proj/github/work/InstalledManagementVersion/data
```

이 설정은 `www-data`가 홈 디렉터리 내용을 열람하지 않고 지정한 경로만 통과하게 하며, 앱의 `data` 디렉터리에 SQLite 기록을 생성·갱신할 수 있게 합니다. Apache 공개 경로는 `/home/user/proj/github/work/InstalledManagementVersion/public`, SQLite 파일 경로는 `/home/user/proj/github/work/InstalledManagementVersion/data/installed-management.sqlite`입니다.

### 2. 이후 최신 버전으로 갱신

최초 clone을 수행한 Linux 사용자 계정으로 GitHub의 `main` 브랜치를 fast-forward 갱신합니다. 저장소 위치에서 공개 파일을 직접 서비스하므로 별도의 파일 복사는 필요하지 않습니다.

```bash
git -C /home/user/proj/github/work pull --ff-only origin main
```

이 갱신 절차는 추적되지 않는 `data/installed-management.sqlite` 파일을 덮어쓰거나 삭제하지 않습니다. 배포 전 데이터베이스를 백업하고, 갱신 후 앱을 확인하세요.

### 3. 먼저 Apache 가상호스트와 PHP 구성을 확인

아래 명령은 **조회만** 합니다. 먼저 현재 활성화된 가상호스트와 PHP 모듈/확장을 확인합니다.

```bash
sudo apache2ctl -S
sudo apache2ctl -M | grep -E 'php|proxy_fcgi'
sudo grep -R -nE 'SetHandler|proxy:unix:.*php|php_module' \
  /etc/apache2/sites-enabled /etc/apache2/conf-enabled
php -v
php -m | grep -Ei 'PDO|pdo_sqlite'
ls -l /run/php/
```

`apache2ctl -S` 결과에서 서비스에 사용할 실제 고객 접속 도메인의 `*:443` HTTPS 가상호스트 항목을 찾습니다. 출력에 표시된 설정 파일 경로는 보통 `/etc/apache2/sites-enabled/...conf`이며, 이 경로가 가리키는 실제 파일을 아래와 같이 확인합니다.

```bash
readlink -f /etc/apache2/sites-enabled/<위에서-확인한-파일명>.conf
```

사이트가 HTTPS 가상호스트를 제공하지 않는 경우 먼저 HTTPS 구성을 준비하세요. HTTP로 이 앱을 외부에 공개하지 마세요. 활성 가상호스트 파일이 어느 것인지 불분명하거나 파일에 다른 서비스의 규칙이 복잡하게 들어 있다면 수정 전에 서버 관리자에게 확인합니다.

PHP CLI에 SQLite 확장이 보인다는 것만으로 Apache에서도 PHP가 실행된다고 단정할 수는 없습니다. PHP가 이미 운영 중인 경우 이 앱을 위해 기존 PHP 모듈이나 PHP-FPM 설정을 다시 설치·전환하지 말고, 해당 HTTPS 가상호스트의 기존 PHP 처리 설정을 그대로 사용합니다. 브라우저에서 PHP 코드가 텍스트로 보이거나 내려받아지는 상태로 서비스를 공개하지 마세요.

#### Apache에서 PHP를 아직 처리하지 않는 경우에만

기존 가상호스트에 이미 `php_module`(mod_php) 또는 PHP-FPM의 `SetHandler`/`proxy_fcgi` 설정이 있는지 확인합니다. 두 방식을 동시에 활성화하지 마세요. 다른 서비스가 이미 사용 중이라면 아래 설치/활성화 명령을 실행하기 전에 관리자와 협의합니다.

Ubuntu 20.04 기본 PHP 7.4 FPM을 새로 구성하기로 승인된 경우, 패키지를 설치하고 Apache의 FastCGI 모듈을 활성화합니다.

```bash
sudo apt install php7.4-fpm php7.4-sqlite3
sudo a2enmod proxy_fcgi setenvif
sudo systemctl enable --now php7.4-fpm
ls -l /run/php/php7.4-fpm.sock
```

그 다음 아래 4단계에서 지정한 **앱의 `<Directory>` 블록 안에만** FPM `FilesMatch` 예시를 추가합니다. 이 설정을 `<VirtualHost>`에 전역으로 두지 않아야 다른 PHP 사이트에 영향을 주지 않습니다. FPM 소켓 파일이 다르면 `ls -l /run/php/` 결과에 맞게 경로를 바꾸세요. 이미 mod_php를 사용한다면 이 FPM 설치와 `FilesMatch` 설정은 하지 않습니다.

### 4. 올바른 HTTPS 가상호스트 파일에 앱 경로 추가

앞 단계의 `readlink -f` 결과로 확인한 **기존 HTTPS 사이트 설정 파일**을 백업하고 엽니다. 예를 들어 실제 결과가 `/etc/apache2/sites-available/company-ssl.conf`였다면 다음과 같습니다. 아래 파일명은 서버에서 확인한 값으로 바꿔야 합니다.

```bash
sudo cp -a /etc/apache2/sites-available/<실제-HTTPS-가상호스트>.conf \
  /etc/apache2/sites-available/<실제-HTTPS-가상호스트>.conf.bak
sudo nano /etc/apache2/sites-available/<실제-HTTPS-가상호스트>.conf
```

파일 안의 해당 도메인 `<VirtualHost *:443>` 블록을 찾습니다. `</VirtualHost>` 바로 위에 다음 설정을 추가합니다. `Require ip`에는 **실제 현장망/VPN에서 서버에 접속할 때 보이는 클라이언트 IP 또는 CIDR**을 적고, 예시 주소는 그대로 사용하지 마세요. 여러 대역이면 `Require ip` 줄을 필요한 만큼 추가합니다.

```apache
    Alias /installed-management /home/user/proj/github/work/InstalledManagementVersion/public

    <Directory /home/user/proj/github/work/InstalledManagementVersion/public>
        DirectoryIndex index.php
        Options -Indexes
        AllowOverride None
        Require ip <실제-현장망-CIDR>
        # 이 앱 전용 PHP-FPM을 새로 구성한 경우에만 아래 블록을 추가합니다.
        # 이미 동작하는 PHP 핸들러가 있다면 추가하지 마세요.
        <FilesMatch "\.php$">
            SetHandler "proxy:unix:/run/php/php7.4-fpm.sock|fcgi://localhost"
        </FilesMatch>
    </Directory>
```

예를 들어 현장망이 `203.0.113.0/24`라고 확인된 경우에만 `Require ip 203.0.113.0/24`와 같이 설정합니다. 스마트폰에서 사용하는 통신/VPN 대역도 접근이 필요한지 네트워크 관리자에게 확인하세요. `Require all granted`로 전체 인터넷에 공개하지 마세요. 이 앱에는 로그인 기능이 없으므로 HTTPS와 네트워크 접근 제한이 필수입니다.

위 예시의 주석 2줄은 FPM을 새로 구성한 경우에만 남기고, 기존 PHP 핸들러를 사용하는 경우 제거합니다. FPM 소켓이 `/run/php/php7.4-fpm.sock`이 아닌 서버에서는 `SetHandler`의 소켓 경로도 실제 경로로 바꿉니다.

### 5. 문법 검사 후 안전하게 반영

먼저 Apache 설정 문법을 검사합니다. `Syntax OK`가 나오지 않으면 reload하지 말고 오류를 수정합니다.

```bash
sudo apache2ctl configtest
```

문법 검사가 통과하면 Apache를 중단하지 않는 graceful reload를 실행하고 상태를 확인합니다.

```bash
sudo systemctl reload apache2
sudo systemctl --no-pager --full status apache2
```

스마트폰 또는 허용된 현장망/VPN 기기에서 `https://<서버주소>/installed-management/`에 접속합니다. 화면이 표시되고 기록 목록/API가 동작하는지 확인합니다. 서버에서 로그를 확인하려면 다음을 사용합니다.

```bash
sudo tail -n 80 /var/log/apache2/error.log
sudo tail -n 80 /var/log/apache2/access.log
```

문제가 생기면 마지막에 변경한 가상호스트 파일을 백업본으로 복원하고 `sudo apache2ctl configtest` 후 `sudo systemctl reload apache2`를 실행합니다. PHP 핸들러 또는 SQLite 확장이 부족한 오류는 Apache 로그에 표시됩니다. 기존 가상호스트나 PHP 처리 설정이 불확실하면 설정을 변경하기 전에 서버 관리자에게 확인하세요.

업그레이드 버전 입력란은 Door LCD 요청에 맞춰 `v0.0.0.9`로 미리 채워져 있으며, 다른 장치의 버전을 입력할 때 수정할 수 있습니다.

조회 메뉴의 `현재 설치된 버전`은 각 방문 기록의 `업그레이드 버전`을 기준으로 검색합니다. 조회 조건은 날짜 범위, 장치명, 현재 설치 버전을 조합할 수 있습니다. 입력 메뉴의 `이전 입력 불러오기`는 최근 100개 기록에서 항목을 선택하며, 이전 방문 날짜 대신 오늘 날짜를 채워 새 현장 입력을 준비합니다.

## 조회 결과 내보내기

조회 메뉴 하단에서 CSV, Excel 통합 문서(`.xlsx`), PDF 형식을 선택할 수 있습니다. 내보내기에는 화면에 표시된 것과 동일한 필터 결과만 포함됩니다. CSV는 한글 인코딩을 위한 UTF-8 BOM을 포함하고, Excel 파일은 외부 패키지나 CDN 없이 브라우저에서 생성합니다.

PDF 선택 시 브라우저 인쇄 창이 열립니다. 인쇄 대상에서 `PDF로 저장`을 선택하면 PDF를 저장할 수 있으며, 같은 조회 결과의 CSV도 함께 다운로드됩니다. `보고서 형식`을 체크하면 문서 제목, 적용한 조회 조건, 기록/장비/랙/모듈 합계, 버전 변경 요약, 현장별 상세 표와 참고 사항을 갖춘 고객 전달용 보고서를 인쇄합니다. 체크하지 않으면 조회 조건과 결과 표 중심의 간단한 PDF가 만들어집니다. PDF 저장 메뉴 표시는 브라우저와 기기별로 다를 수 있습니다.

## 데이터 위치와 백업

기록은 `data/installed-management.sqlite`에 저장됩니다. 데이터베이스가 웹 공개 디렉터리(`public`) 밖에 있으므로 HTTP로 직접 접근할 수 없습니다. 백업 시 SQLite 파일을 복사하고, 일관된 백업이 필요하면 SQLite 백업 도구 또는 서비스 점검 시간을 이용하세요. `data` 디렉터리를 공개 저장소에 커밋하지 마세요.
