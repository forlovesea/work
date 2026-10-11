# Windows EXE 빌드

현재 구현은 `release_entry.py`와 `KoreanStockBot.spec`을 사용합니다. 하나의 공통 라이브러리 폴더를 공유하는 다섯 EXE를 생성합니다.

- KoreanStockBotETF.exe: ETF GUI
- KoreanStockBotStock.exe: 단일 종목 GUI
- KoreanStockBotPaper.exe: 모의 GUI
- trader.exe: GUI가 호출하는 거래 엔진
- research.exe: 거래 엔진이 호출하는 ETF 자료 수집기

`app_paths.py`는 소스 실행에서는 프로젝트 폴더, EXE에서는 실행 파일 폴더를 설정·장부 공통 경로로 선택합니다. 소스에서는 Python + .py, 배포에서는 전용 작업 EXE를 호출합니다. 거래·수집기에는 콘솔 출력을 유지하고 GUI가 숨김 실행하여 상태 파이프를 읽습니다.

## 빌드

프로젝트 폴더의 PowerShell에서 실행합니다.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -X utf8 -m unittest -v
powershell -NoProfile -ExecutionPolicy Bypass -File build_release.ps1
```

`Release/KoreanStockBot/`에 결과가 생성됩니다. 기존 배포 폴더에 runtime 또는 research가 있으면 덮어쓰지 않고 중단합니다. 운용 중인 배포 폴더를 빌드 출력 위치로 사용하지 마세요. 새 체크아웃에서 빌드하세요.

## 오프라인 검증

```powershell
Release\KoreanStockBot\trader.exe --self-test
Release\KoreanStockBot\research.exe --self-test
Release\KoreanStockBot\trader.exe --gui-smoke
```

인증정보 읽기·API 호출·주문 없이 패키지 의존성, 암호화 왕복, 모의 계산, 세 GUI의 그래프·달력 동작을 확인합니다. 실제 인증을 사용하는 KRX 수집과 토스 체결의 검증을 대신하지 않습니다.

## 전달·업데이트

EXE만 분리하지 말고 `_internal`, 설정, 보조 EXE를 포함한 폴더 전체를 전달합니다. 개인 runtime·캐시·키는 배포물에 포함하지 않습니다. 기존 계좌를 계속 운용할 때는 거래 중지·주문 확인 후 기존 설정과 장부를 보존하는 이전이 필요합니다. 다른 폴더에서 같은 계좌 봇을 동시에 실행하지 않습니다.

PyInstaller는 파이썬 환경과 의존성을 묶는 배포 도구이며 소스코드 보호나 수익성을 보장하지 않습니다. 코드 서명은 적용하지 않았습니다. Windows 64비트에서 빌드하며 다른 운영체제용 EXE는 아닙니다.
# 버전별 배포

`powershell -ExecutionPolicy Bypass -File build_release.ps1`로 빌드합니다.
`app_version.py`의 버전과 기존 `Release/v버전` 폴더를 비교하여 다음 사용 가능한 패치 버전을 선택합니다.
EXE 이름·창 제목·Windows 파일 속성에 같은 버전이 적용됩니다.
출력은 `Release/v버전/KoreanStockBot`이며, `python package_release.py`로 해당 버전 ZIP을 만듭니다.
PyInstaller를 직접 실행하기 전에 `python prepare_version.py`로 버전 리소스를 생성해야 합니다.

