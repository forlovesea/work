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

기존 Apache 가상호스트, 원격제어 서버, 축전지 감시 서버 설정을 변경하지 않고 별도 경로로 추가할 수 있습니다. Apache 설정 변경은 서버 관리자가 검토 후 적용해야 합니다.

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

저장소 전체 파일을 작업 트리에 펼치지 않고 `InstalledManagementVersion`만 sparse checkout으로 내려받습니다. 아래 checkout 경로(`/opt/installed-management-version-source`)가 아직 없어야 합니다.

```bash
sudo git clone --depth 1 --filter=blob:none --sparse --branch main \
  https://github.com/forlovesea/work.git \
  /opt/installed-management-version-source
sudo git -C /opt/installed-management-version-source \
  sparse-checkout set InstalledManagementVersion
```

공개 웹 파일만 Apache 서비스 경로에 복사합니다. SQLite 데이터는 공개 디렉터리 밖에 두기 위해 별도의 쓰기 가능 디렉터리를 만듭니다.

```bash
sudo install -d -o root -g root -m 755 /opt/installed-management-version/public
sudo cp -a \
  /opt/installed-management-version-source/InstalledManagementVersion/public/. \
  /opt/installed-management-version/public/
sudo install -d -o www-data -g www-data -m 770 /opt/installed-management-version/data
sudo chown -R root:root /opt/installed-management-version/public
sudo find /opt/installed-management-version/public -type d -exec chmod 755 {} \;
sudo find /opt/installed-management-version/public -type f -exec chmod 644 {} \;
```

`www-data`에는 `data` 디렉터리 쓰기 권한만 주고 `public`에는 쓰기 권한을 주지 않습니다. 앱의 공개 경로는 `/opt/installed-management-version/public`, SQLite 파일 경로는 `/opt/installed-management-version/data/installed-management.sqlite`입니다.

### 2. 이후 최신 버전으로 갱신

서버에 새 코드를 내려받을 때는 sparse checkout 저장소를 fast-forward로 갱신한 뒤 공개 파일만 복사합니다.

```bash
sudo git -C /opt/installed-management-version-source pull --ff-only origin main
sudo cp -a \
  /opt/installed-management-version-source/InstalledManagementVersion/public/. \
  /opt/installed-management-version/public/
sudo chown -R root:root /opt/installed-management-version/public
sudo find /opt/installed-management-version/public -type d -exec chmod 755 {} \;
sudo find /opt/installed-management-version/public -type f -exec chmod 644 {} \;
```

이 갱신 절차는 `data` 디렉터리와 SQLite 파일을 덮어쓰거나 삭제하지 않습니다. 배포 전 데이터베이스를 백업하고, 갱신 후 앱을 확인하세요.

### 3. Apache 연결

PHP 7.4 이상과 PDO SQLite가 아직 설치되어 있지 않은 경우에만 서버 관리자가 별도로 설치 여부를 검토합니다. 설치된 PHP 핸들러(Apache 모듈 또는 PHP-FPM)에 앱의 `public` 디렉터리를 연결해야 합니다. 예를 들어 기존 가상호스트 설정에 다음 Alias를 추가할 수 있습니다.

```apache
Alias /installed-management /opt/installed-management-version/public
<Directory /opt/installed-management-version/public>
    DirectoryIndex index.php
    Options -Indexes
    AllowOverride None
    # 실제 현장망 또는 VPN 대역으로 바꿔서 사용하세요.
    Require ip 192.168.0.0/16
</Directory>
```

PHP 핸들러가 이미 구성되어 있어야 하며, 경로를 적용한 뒤 기존 가상호스트와 서비스의 상태를 확인합니다. 접속 주소는 `https://<서버주소>/installed-management/` 형태입니다. 이 앱은 로그인 기능을 포함하지 않으므로 사내망/VPN으로 접근을 제한하고 HTTPS를 사용하세요. 외부 공개가 필요하면 기존 인증 정책에 맞는 Apache 접근 제어를 먼저 적용해야 합니다.

업그레이드 버전 입력란은 Door LCD 요청에 맞춰 `v0.0.0.9`로 미리 채워져 있으며, 다른 장치의 버전을 입력할 때 수정할 수 있습니다.

조회 메뉴의 `현재 설치된 버전`은 각 방문 기록의 `업그레이드 버전`을 기준으로 검색합니다. 조회 조건은 날짜 범위, 장치명, 현재 설치 버전을 조합할 수 있습니다. 입력 메뉴의 `이전 입력 불러오기`는 최근 100개 기록에서 항목을 선택하며, 이전 방문 날짜 대신 오늘 날짜를 채워 새 현장 입력을 준비합니다.

## 조회 결과 내보내기

조회 메뉴 하단에서 CSV, Excel 통합 문서(`.xlsx`), PDF 형식을 선택할 수 있습니다. 내보내기에는 화면에 표시된 것과 동일한 필터 결과만 포함됩니다. CSV는 한글 인코딩을 위한 UTF-8 BOM을 포함하고, Excel 파일은 외부 패키지나 CDN 없이 브라우저에서 생성합니다.

PDF 선택 시 브라우저 인쇄 창이 열립니다. 인쇄 대상에서 `PDF로 저장`을 선택하면 PDF를 저장할 수 있으며, 같은 조회 결과의 CSV도 함께 다운로드됩니다. `보고서 형식`을 체크하면 문서 제목, 적용한 조회 조건, 기록/장비/랙/모듈 합계, 버전 변경 요약, 현장별 상세 표와 참고 사항을 갖춘 고객 전달용 보고서를 인쇄합니다. 체크하지 않으면 조회 조건과 결과 표 중심의 간단한 PDF가 만들어집니다. PDF 저장 메뉴 표시는 브라우저와 기기별로 다를 수 있습니다.

## 데이터 위치와 백업

기록은 `data/installed-management.sqlite`에 저장됩니다. 데이터베이스가 웹 공개 디렉터리(`public`) 밖에 있으므로 HTTP로 직접 접근할 수 없습니다. 백업 시 SQLite 파일을 복사하고, 일관된 백업이 필요하면 SQLite 백업 도구 또는 서비스 점검 시간을 이용하세요. `data` 디렉터리를 공개 저장소에 커밋하지 마세요.
