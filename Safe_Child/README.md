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
dotnet run --project .\Tests\MessageChecks\MessageChecks.csproj -c Release
dotnet run --project .\Tests\GridBindingChecks\GridBindingChecks.csproj -c Release
```

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
