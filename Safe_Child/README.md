# Safe Child

Safe Child는 Windows 10/11용 보호자 관리 WinForms 프로그램입니다. 도메인/포트 차단, 시간 예약, 방문 기록 조회, 보호자 메시지, 같은 네트워크의 스마트폰 QR 제어 기능을 포함합니다.

## 지원 환경

- Windows 10/11 x64
- .NET 8 SDK
- Visual Studio 2022 또는 Visual Studio Code

이 프로젝트는 `net8.0-windows`와 Windows Forms를 사용하므로 Linux/macOS에서는 빌드 대상이 아닙니다. 다른 Windows PC에서 내려받은 뒤 NuGet 패키지는 `dotnet restore` 또는 `dotnet build` 과정에서 자동 복원됩니다.

## 내려받은 뒤 빌드

```powershell
git clone https://github.com/forlovesea/work.git
cd work\Safe_Child
dotnet restore .\SafeChild.sln
dotnet build .\SafeChild.sln -c Release
```

빌드 결과는 다음 위치에 생성됩니다.

```text
bin\Release\net8.0-windows\SafeChild.exe
```

## 실행

URL/도메인 차단 목록에는 시간표와 일시 허용을 반영한 **설정 상태**와 파일을 직접 읽은 **hosts 실제 상태**가 별도로 표시됩니다. hosts 상태는 적용 시도 직후와 5초마다 확인하며, **hosts 상태 새로고침**으로 즉시 확인할 수 있습니다. 상태는 굵은 글씨와 배경색으로 구분합니다. 설정과 일치하는 차단은 빨강, 해제는 초록, 설정 불일치·충돌·확인 실패는 주황, 확인 전은 회색입니다. 상태 셀에 마우스를 올리면 등록 도메인과 `www.` 주소의 실제 매핑을 볼 수 있습니다. Safe Child 관리 영역 밖의 항목도 검사합니다.

이 표시는 hosts 파일 기준입니다. ‘해제’는 해당 주소의 hosts 차단 항목이 없다는 뜻이며 실제 브라우저 접속 성공을 보장하지 않습니다. 재부팅 전후 동작이 다르다면 먼저 설정 상태와 hosts 실제 상태가 일치하는지 확인하세요.

Safe Child는 `hosts` 파일과 Windows 방화벽 규칙을 관리하므로 실제 보호 기능을 적용하려면 관리자 권한이 필요합니다.

```powershell
Start-Process -FilePath .\bin\Release\net8.0-windows\SafeChild.exe -Verb RunAs
```

처음 실행하면 8자 이상의 관리자 비밀번호를 설정합니다. 창의 X 버튼은 트레이로 숨김 처리되며, 완전히 종료하려면 앱 내부의 프로그램 종료 기능을 사용합니다.

## 개발 실행

디버그 빌드:

```powershell
dotnet build .\SafeChild.csproj -c Debug
```

VS Code를 사용하는 경우 `SafeChild.code-workspace`를 열고 `Ctrl+Shift+B`로 빌드할 수 있습니다. `.vscode/tasks.json`에는 관리자 권한 실행 작업도 포함되어 있습니다.

## 검증 명령

아래 명령으로 핵심 로직 검사를 실행할 수 있습니다.

```powershell
dotnet run --project .\Tests\TimingChecks\TimingChecks.csproj -c Release
dotnet run --project .\Tests\HostsChecks\HostsChecks.csproj -c Release
dotnet run --project .\Tests\MessageChecks\MessageChecks.csproj -c Release
dotnet run --project .\Tests\GridBindingChecks\GridBindingChecks.csproj -c Release
dotnet run --project .\Tests\MobileChecks\MobileChecks.csproj -c Release
dotnet run --project .\Tests\MobileUiChecks\MobileUiChecks.csproj -c Release
```

## 스마트폰에서 사이트별 보호 설정

PC의 **스마트폰 제어 → QR 연결 시작**을 누른 뒤 같은 공유기에 연결된 휴대폰으로 QR을 스캔합니다. 관리자 비밀번호로 인증하면 다음 작업을 할 수 있습니다.

- 사이트 목록·현재 상태 조회, 사이트 추가·주소 변경·삭제
- 사이트별 차단 선택 켜기/끄기
- 항상 차단, 시작·종료 날짜 지정, 경과 시간 기준 차단, 월~일 개별 반복 시간표
- 기존 전체 일시 허용(최대 24시간)과 즉시 보호 복원

일정은 **PC 현지 시각** 기준이며 모바일 화면에 PC 시각과 시간대를 표시합니다. 요일별로 하루 한 구간을 지정하며 종료가 시작보다 이르면 다음 날까지 이어집니다. 시작·종료가 같으면 해당 요일은 종일 차단합니다. 사용하지 않는 요일에도 전날 시작한 차단은 종료 시각까지 이어질 수 있습니다.

모바일에서 저장한 규칙은 PC 목록에도 반영되고 기존 보호 로직으로 적용됩니다. 전체 일시 허용 중에는 규칙만 저장하고, 일시 허용 종료 후 차단에 반영합니다. 디스크 저장 실패 시 원래 규칙을 유지하며, 저장 후 차단 적용 실패는 별도로 표시합니다. PC나 다른 휴대폰에서 먼저 변경한 규칙은 덮어쓰지 않으므로 목록을 새로고침하고 다시 편집하세요.

기존 평일·주말 설정은 계속 호환됩니다. PC 시간 설정 창의 **월~일 각각 설정**으로 개별 일정을 편집할 수 있습니다. 경과 시간은 같은 설정을 저장하면 유지되고, 다시 시작 선택 또는 시간 방식·분 값 변경 시 새로 계산합니다.

기본값은 내부 네트워크 전용입니다. 관리자 모드에서 **외부 접속 사용**을 켜고 외부 HTTPS 주소와 PFX 인증서를 등록하면 포트포워딩을 통한 외부 접속을 지원합니다. 모바일 인증은 15분 동안 유지됩니다. 외부 접속은 이 PC의 관리자 비밀번호만 사용하며 마스터 비밀번호로는 로그인하지 않습니다.

외부 연결 준비와 사용 순서는 [외부 접속 안내](REMOTE_ACCESS.md)를 참고하세요.

`MobileChecks`는 실제 보호 설정 파일과 hosts/방화벽을 변경하지 않고 메모리 설정과 임시 로컬 HTTPS 서버로 검증합니다. 외부 Host·Origin·TLS 이름을 유지한 채 로컬 포트로 연결해 포트포워딩 상황도 검증합니다. `MobileUiChecks`는 실제 스마트폰 설정 페이지의 관리자 권한·설정 복원·초기화·입력 상태를 검증합니다. Windows TLS 인증 기능이 제한된 실행 환경에서는 일반 Windows 터미널에서 실행하세요.

## 배포 파일 생성

설치 파일과 self-contained 앱 묶음은 다음 스크립트로 생성합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Deployment\Build-Release.ps1
```

생성 위치:

```text
Final\_Release\
```

`Final\_Release`는 빌드 산출물이므로 Git에는 포함하지 않습니다. 새 PC에서는 위 스크립트로 언제든 다시 만들 수 있습니다.

## 브라우저 확장

방문 감지와 보호자 메시지 기능은 Chrome/Edge 확장이 필요합니다. 앱에서 확장 폴더 열기 기능을 사용하거나 `BrowserExtension` 폴더를 브라우저의 개발자 모드에서 압축해제된 확장으로 로드합니다.

## 주요 구성

- `SafeChild.csproj`: 메인 WinForms 프로젝트
- `SafeChild.sln`: Visual Studio 솔루션
- `BrowserExtension/`: Chrome/Edge 확장
- `Deployment/`: 설치 파일 생성 스크립트
- `Tests/`: 콘솔 기반 검증 프로젝트
