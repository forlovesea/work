# SafeChild Windows 10/11 x64 배포본

## 다른 PC에 설치

1. `SafeChild-Setup-Win10-x64.exe`를 대상 PC에 복사합니다. 파일명의 Win10은 배포 프로필 이름이며 Windows 11 x64에도 동일한 설치 파일을 사용합니다. 이 설치 파일 하나에 앱과 런타임이 포함되어 있습니다.
2. 설치 파일을 더블클릭하고 관리자 권한 요청을 허용합니다. 대안으로 `Final\_Release` 폴더 전체를 복사한 후 `Install.cmd`를 실행해도 됩니다.
3. 바탕화면의 SafeChild 바로가기를 실행합니다.
4. 최초 실행 시 관리자 비밀번호를 설정합니다. 기존 설치를 업데이트하면 기존 설정과 접속 기록을 유지합니다.

설치 위치: `C:\Program Files\SafeChild`
설정·기록 위치: `C:\ProgramData\SafeChild`

Windows 10/11 **64비트**용입니다. 32비트 Windows와 ARM 전용 배포본은 포함하지 않습니다. .NET 8 런타임, Windows Desktop/ASP.NET Core 런타임, SQLite 네이티브 라이브러리를 포함하므로 대상 PC에 .NET SDK, VS Code, Visual Studio 또는 별도 .NET 런타임을 설치할 필요가 없습니다. 설치 자체는 인터넷 연결 없이 가능합니다.

설치 프로그램은 앱 파일 복사 및 바탕화면/시작 메뉴 바로가기 생성을 수행합니다. 자동 실행은 앱에서 직접 설정합니다. **관리자 모드 → 창 맨 아래 중앙 → 재부팅후 자동실행**을 누르면 해당 PC의 작업 스케줄러에 등록됩니다. 재부팅 후 버튼을 누른 Windows 계정에 로그인하면 관리자 권한으로 실행되며 앱의 관리자 모드는 잠금 상태를 유지합니다. Windows 계정 비밀번호는 저장하지 않습니다. 다른 Windows 계정이나 로그인 전에는 실행되지 않습니다. 프로그램 경로를 옮긴 경우 버튼을 다시 눌러 갱신하세요. 자동실행만 해제하려면 창 맨 아래 중앙의 **자동실행 삭제** 버튼을 누르세요. 다음 재부팅 후 해당 계정으로 로그인할 때 자동으로 시작하지 않습니다. 설정초기화를 누르는 경우에도 현재 계정의 자동 실행이 해제됩니다.

현재 개발 PC의 비밀번호 설정 파일, 접속 기록, QR 인증서 등 사용자 데이터는 배포본에 포함하지 않습니다. 소스에 이미 구현된 마스터 인증 기능은 그대로 포함됩니다.

## 포함된 설치 파일과 실행 방법

- `SafeChild-Setup-Win10-x64.exe`: 앱과 필요한 런타임을 포함한 통합 설치 파일입니다.
- `Install.cmd`, `Install.ps1`, `Payload.zip`: 폴더 단위로 전달할 때 사용하는 대체 설치 구성입니다. 세 파일을 같은 폴더에 두고 `Install.cmd`를 실행하세요.
- `App`: 실행 파일과 .NET/SQLite 구성요소, 브라우저 확장이 들어 있습니다. 일반적인 설치는 위 통합 설치 파일을 사용하세요.
- `SHA256SUMS.txt`: 배포 파일 무결성 확인용 SHA-256 목록입니다.

설치 후 바탕화면의 **SafeChild**를 실행하고 Windows 관리자 권한 요청을 허용하세요. 관리자 비밀번호 설정 후 상단의 **관리자 모드**에서 인증하면 보호 설정과 창 하단의 자동실행 버튼을 사용할 수 있습니다. X 버튼이나 최소화는 앱을 종료하지 않고 트레이에 숨깁니다. 다시 열 때는 트레이 아이콘을 사용하고, 종료할 때는 관리자 모드의 **프로그램 종료**를 누르세요.

## 전달 메시지

앱 자체에서 팝업을 표시하지만 접속 감지는 현재 Chrome/Edge 확장이 필요합니다. 관리자 모드 → 전달 메시지 → 확장 폴더 열기를 누른 뒤 Chrome의 `chrome://extensions` 또는 Edge의 `edge://extensions`에서 개발자 모드를 켜고 압축해제된 확장 프로그램 로드로 설치된 `BrowserExtension` 폴더를 선택하세요. 자녀가 사용하는 각 프로필에 설치해야 합니다. 자세한 안내는 `App\BrowserExtension\README.md`를 참고하세요.

## 배포 옵션

시간 설정에서 **반복 시간 (평일·주말)**을 선택하면 월~금과 토·일의 차단 시간을 각각 저장해 매주 반복합니다. 평일/주말의 ‘사용’ 체크로 요일 그룹을 켜거나 끌 수 있습니다. 종료 시각이 시작보다 이르면 다음 날까지 이어지고, 두 시각이 같으면 해당 요일은 종일 차단합니다. 예: 금요일 22:00~07:00은 토요일 07:00까지 차단합니다. 반복 일정은 PC 현지 날짜·시각을 사용하므로 시계 변경의 영향을 받습니다. URL/도메인과 포트에 동일하게 적용되며 테이블에 다음 시작/해제까지 남은 시간이 표시됩니다.

- Release, win-x64, Optimize=true
- SelfContained=true: 런타임 포함
- PublishReadyToRun=true: 시작 시 JIT 작업 감소
- TieredCompilation/TieredPGO=true, 워크스테이션 GC
- PublishTrimmed=false: WinForms/리플렉션 호환성 유지
- PublishSingleFile=false: 외부 확장 및 네이티브 파일을 안정적인 설치 경로에 유지
- DebugType=none, DebugSymbols=false

프로필: `Properties\PublishProfiles\Windows10-x64.pubxml`
개발 PC에서 재생성: `powershell -NoProfile -ExecutionPolicy Bypass -File .\Deployment\Build-Release.ps1`

## 업데이트 및 제거

업데이트 전에는 관리자 모드의 프로그램 종료 버튼으로 앱을 종료하세요. X 버튼은 트레이로 숨깁니다. 기존 앱이 멈춘 상태라면 작업 관리자에서 종료한 후 설치하세요.

이 설치 스크립트는 Windows 앱 목록에 제거 프로그램을 등록하지 않습니다. 제거하려면 먼저 앱 관리자 모드의 설정초기화로 차단 규칙을 해제하고 앱을 종료한 뒤 설치 폴더와 바로가기를 삭제합니다. 설정초기화는 비밀번호와 접속 기록을 지우지 않습니다. 설정과 접속 기록까지 지우려는 경우에만 ProgramData의 SafeChild 폴더를 별도로 삭제하세요.

배포본은 코드 서명되지 않았습니다. 대상 Windows 10 실제 PC에서 설치·브라우저 확장·도메인/포트 차단·종료·재부팅 동작을 확인한 후 사용하세요.

참고: https://learn.microsoft.com/en-us/dotnet/core/deploying/
