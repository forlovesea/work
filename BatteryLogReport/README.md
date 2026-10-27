# 축전지 로그 보고서 — Windows x64 / Android

## Windows 64비트

[Windows 배포 ZIP 1.0.1](releases/BatteryLogReport-Windows-x64-1.0.1.zip)을 **전체 압축 해제**한 다음 `BatteryLogReport.exe`를 실행합니다. Java 런타임이 포함되어 있어 별도 Java/Python 설치가 필요 없습니다. Word가 없어도 DOCX를 생성할 수 있습니다.

대상: **Windows 7 SP1 이상 64비트 전용**. EXE와 포함 JVM 모두 x64입니다. Windows 7 SP1을 명시한 [BellSoft 지원 구성](https://bell-sw.com/pages/supported-configurations/)에 따라 Liberica Java 8을 포함하고, Java 8 API와 Windows 7 실행 API만 사용하도록 빌드했습니다. 실제 실행 검증은 현재 Windows 10 계열 환경에서 수행했으며 **실제 Windows 7 장비에서는 미검증**입니다.

설치장소별·호기별 다중/추가 업로드, 파일명·크기·등록 상태 표시, 등록 목록 자동 복원, 두 보고서 생성 및 저장 폴더 열기를 제공합니다. 로그 분석과 문서 생성 코드는 Android와 공유합니다. 자세한 사용법은 [Windows 안내](windows/README-Windows.txt)를 참고하세요.

Windows 빌드 및 검증:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\download-tools.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\build-windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\test-windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\package-windows.ps1
```

다운로드 스크립트는 공식 배포처의 런타임과 빌드 도구를 내려받아 검증합니다. 빌드에는 JDK 17 이상이 필요하며, `JAVA_HOME` 또는 이 작업 폴더의 기존 도구 경로를 사용합니다. 실행 프로그램은 포함된 Java 8을 사용합니다.

## Android

설치 파일: `releases/BatteryLogReport-1.0.1.apk` (Android 8.0 이상)

1.0.1 변경: AC 정전 추정 보고서의 2-3절 원본 기록 표에 첫 양수 전류 시점과 이후 충전 유지 구간의 실측값을 최대 4개 추가합니다. 방전 후 충전 구간이 확인되는 첫 주기를 표시하며, 긴 구간은 시작·중간·끝에서 발췌합니다. 양수 전류가 없으면 충전 행을 넣지 않습니다. 0 A·재방전·10분 초과 기록 공백을 넘어서 충전이 유지되었다고 설명하지 않습니다. 본문에는 실측 시각, 양수 전류 기록 수와 SOC 증가 근거를 함께 기재합니다.

제공된 Word 문서 2개를 내장 템플릿으로 사용하며 인터넷 연결 없이 ZIP 로그를 분석합니다. 원본 자료는 수정하지 않습니다.

## 사용 순서

1. APK를 휴대폰에 복사해 설치합니다.
2. **설치장소 추가**에서 `용인외사` 등 장소명을 입력합니다.
3. 호기를 선택하고 **로그파일 업로드**에서 ZIP 파일을 하나 또는 여러 개 선택합니다.
4. 같은 장소·호기에 추가할 로그는 해당 장소·호기를 선택한 뒤 다시 업로드합니다.
5. 상단 **업로드 상황**에서 호기별 파일명·크기·식수를 확인합니다.
6. **보고서 생성**을 누르면 등록된 모든 설치장소를 포함하는 두 문서가 생성됩니다.
7. **보고서 2개 폴더에 저장** 또는 **보고서 2개 공유**를 누릅니다. Word 앱이 있으면 앱에서 바로 열 수 있습니다.

생성 파일명:

- `축전지 충·방전 로그 분석.docx`
- `AC 정전시 LFP에서 AC 정전을 유추.docx`

저장할 때마다 새 하위 폴더를 만들어 이전 보고서를 덮어쓰지 않습니다. 앱의 열기·공유 버튼은 마지막으로 생성한 보고서를 가리킵니다. 로그를 추가·삭제한 뒤에는 보고서 생성을 다시 눌러야 변경 사항이 반영됩니다.

## 파일과 축전지 식수

- `perfmg_minute.csv`가 들어 있는 ZIP + `perfmg_uncertain.csv`가 들어 있는 ZIP 한 쌍을 축전지 1식으로 취급합니다.
- 파일을 하나씩 올릴 수 있습니다. 한 종류만 등록해도 보고서는 생성되지만 나머지 항목은 미제공·확인 불가로 표시합니다.
- 같은 종류를 여러 개 올리면 선택한 호기부터 해당 종류가 비어 있는 호기에 순서대로 배정합니다. 두 종류를 각각 2개 올리면 2식입니다.
- ZIP 파일명이 같아도 덮어쓰지 않습니다. 내용까지 동일한 파일을 다시 올리면 별도 호기로 등록하고 중복 안내를 표시합니다. 실제 장비별 짝이 맞는지 상황창에서 확인하세요.
- 잘못 배정한 호기는 **호기 로그 삭제** 후 원하는 호기를 선택하여 다시 업로드합니다.
- CSV 내부에 장비 일련번호가 없으므로 서로 다른 장비의 ZIP을 내용만으로 자동 연결할 수 없습니다. 여러 장비의 파일을 한꺼번에 선택할 때 같은 종류 내 선택 순서를 맞추거나 호기별로 한 쌍씩 등록하세요.
- 한 번에 최대 40개, ZIP당 64 MB, 압축 해제 CSV당 128 MB까지 처리합니다.

## 분석 기준

- Huawei CSV의 `Lithium Battery Group / Current, SOC, Battery Status`, `Digital Power / Total DC Load Power, Power Supply Source`를 사용합니다.
- 전류 A, SOC %, 부하 kW/W 단위를 검증하고 부하는 W로 변환합니다.
- No Data, 잘못된 시각·수치·단위는 제외하고 보고서에 제외 건수를 표시합니다. 동일 항목·시각의 서로 다른 값은 오류로 처리합니다.
- 통계는 전체 minute 기록에서 계산합니다. DC 부하는 같은 실측 시각의 그룹 전류가 음수인 지점만 사용합니다.
- 방전 구간은 음수 전류가 이어지는 구간으로 구분하며 10분 초과 기록 공백은 분리합니다.
- SOC 100% 회복은 방전 후 양수 충전 전류가 나타난 이후, 다음 방전 전까지의 SOC 기록에서 확인합니다. 방전 전 100%를 회복으로 오인하지 않습니다.
- 상태 변경 시각은 minute 실측 시각과 다를 수 있어 방전 구간 전후 10분 범위에서 연결합니다. 상태 비교 표에는 첫 관련 전환 시각을 표시합니다.
- AC 정전은 간접 추정입니다. Unknown 값을 AC 정상·복전의 직접 증거로 쓰지 않습니다. 알람 ZIP은 지원 입력에 포함되지 않아 알람이 없었다는 결론을 쓰지 않습니다.
- 예시 문서의 문서 스타일·테마·번호 정의·용지·여백은 유지합니다. 장소·식수·수치·날짜·판정 문구·표·그래프는 실제 로그에 맞춰 갱신합니다. 3식 이상이면 표를 2식 단위로 나누고 호기별 분석을 반복합니다. 데이터 양에 따라 페이지 수와 줄바꿈은 달라질 수 있습니다.

## 개발 및 검증

Java 17 / Android SDK 35 / Gradle 8.11.1 / Android Gradle Plugin 8.9.2. 외부 런타임 라이브러리 및 인터넷 권한 없이 동작합니다.

현재 작업 폴더의 `../BatteryWatch/android-app/.toolchain`과 `.gradle-home`을 재사용합니다. 도구 위치가 다르면 `BATTERY_REPORT_TOOLCHAIN` 환경변수 또는 Android Studio를 사용하세요.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

`test.ps1`은 제공된 실제 로그와 합성 경계 사례를 검사하고 `qa/generated`에 검증용 보고서를 생성합니다. 보고서의 이미지 참조 무결성과 템플릿 유지 대상 파트의 바이트 동일성도 검사합니다. `signing` 폴더는 이후 동일 앱 업데이트 빌드에 사용하므로 별도로 보관하고 버전 관리에는 포함하지 않습니다.

검증 결과는 `VALIDATION.md`를 참고하세요.
