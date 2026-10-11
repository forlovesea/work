# KoreanStockBot 개발 상세서

비개발자도 이해할 수 있는 소스코드·실행·검증·배포 안내

작성 기준: 2026-10-11 / Python 3.10 이상 / Windows

EXE 배포 추가: release_entry.py, app_paths.py, KoreanStockBot.spec, build_release.ps1을 구현했습니다. 최신 빌드 방법은 7장과 EXE_BUILD_GUIDE.md를 참고하세요.

## 1. 이 프로그램은 무엇인가요?

국내 주식과 코스닥 관련 ETF의 데이터를 확인하고 정해진 규칙에 따라 매수·매도를 판단하는 Python 프로그램입니다. 화면을 담당하는 GUI와 거래를 담당하는 엔진을 분리했습니다. 사람이 GUI의 실전 시작을 승인하면 엔진은 조건에 따라 실제 주문을 전송합니다.

모의매매는 합성 데이터 또는 과거 CSV로 실험합니다. 실전의 읽기 전용 점검은 계좌와 시세를 조회하지만 실제 주문이나 가상 체결을 만들지 않습니다. 실전 자동주문과 모의매매는 서로 다른 실행 모드입니다.

자동 테스트 73개와 세 GUI의 창·기간 선택·그래프·달력 동작을 확인했습니다. EXE의 오프라인 의존성·암호화·GUI 검사도 통과했습니다. 실제 계좌 연결·체결, API HUB 실키 호출, 전략 수익성 및 별도 깨끗한 PC에서의 실행은 검증하지 않았습니다. 10%는 목표이며 수익 보장이 아닙니다.

## 2. 용어부터 이해하기

| 용어 | 쉬운 설명 |
|---|---|
| 소스코드 | 사람이 작성한 프로그램 설명서. 이 프로젝트에서는 .py 파일 |
| Python | .py 파일을 읽고 실행하는 프로그램이자 언어 |
| GUI | 버튼·입력칸·그래프가 있는 화면 |
| API | 프로그램이 증권사나 데이터 제공 서비스와 대화하는 통로 |
| JSON | 설정이나 실행 기록을 항목과 값으로 저장하는 텍스트 형식 |
| 가상환경 | 이 프로젝트에 필요한 Python 패키지만 모아 두는 .venv 폴더 |
| 프로세스 | 실행 중인 프로그램 한 개. GUI·거래·자료 수집이 분리됨 |
| 테스트 | 실제 돈을 쓰지 않고 가짜 응답으로 동작을 검사하는 코드 |
| 컴파일 | 소스코드를 실행하기 좋은 형태로 변환. Python의 문법 검사와 EXE 묶기는 서로 다름 |

## 3. 전체 구조와 실행 흐름

화면 → 거래 프로세스 → 토스 API → 주문·체결 확인 → 장부 저장 → 화면 갱신 순서입니다.

```text
start.bat      → app.py --mode paper → engine.py (모의매매)
start_etf.bat  → app.py --mode etf   → live_gui.py → live.py --etf
start_live.bat → app.py --mode stock → live_gui.py → live.py

실전 공통: live.py → broker.py → 토스증권 API
ETF 전략: etf_live.py → etf_research.py → 완성된 분석 JSON
자동 수집: auto_research.py → auto_data.py / research_sources.py
분석 생성: build_research.py → research/auto_latest.json
실전 기록: runtime/etf_live_state.json 또는 runtime/live_state.json
```

GUI는 subprocess로 거래 프로세스를 시작합니다. 거래가 오래 걸려도 화면이 멈추지 않도록 로그 읽기는 별도 스레드와 큐를 사용합니다. Tkinter 화면 변경은 메인 스레드에서 처리합니다. 실전 API를 GUI 버튼 콜백 안에서 직접 오래 실행하지 않는 것이 유지보수 원칙입니다.

자료 수집도 별도 프로세스로 실행됩니다. 수집 프로세스에는 TOSS_로 시작하는 환경변수를 전달하지 않습니다. GUI와 실전 엔진은 파일을 통해 상태를 공유하므로 경로와 파일 형식의 일치가 중요합니다.

## 4. 소스파일별 역할

| 파일 | 하는 일 / 수정할 때 |
|---|---|
| app.py | 공통 GUI, 다크 테마, 수익률 그래프, 기간 선택·달력. 디자인 수정 위치 |
| live_gui.py | 인증 설정, 계좌 조회, 거래 프로세스 시작·중지, 장부를 화면에 표시 |
| engine.py | 모의매매 Config·Bar·PaperEngine, CSV 읽기와 가상 체결 |
| live.py | 실전 공통 안전 검사·주문·체결 반영·손실 제한·장부·프로세스 잠금 |
| broker.py | 토스 OAuth 인증, 조회·주문·취소 HTTP 요청 |
| etf_live.py | 상위 ETF 후보 선택, 기존 보유분 유지와 재무·뉴스 매매 조건 |
| etf_research.py | 순자산 순위, 편입 비중, 재무·뉴스 점수, 분석 최신성 검사 |
| auto_research.py | 수집 프로세스 실행·갱신 주기·실패 재시도·시간 제한 |
| auto_data.py | pykrx로 KRX 자료 수집, 총순자산과 구성종목 정규화 |
| research_sources.py | DART 기업코드·재무자료, 네이버 뉴스 조회와 캐시 |
| build_research.py | 수집 자료를 분석해 JSON과 요약 CSV 생성 |
| credentials.py | Windows DPAPI 인증정보 암호화 저장·불러오기 |
| launch_live.py | 기존 콘솔 방식의 설정과 실전 실행. GUI와 별도로 유지 |
| prepare_etf.py | 수동 CSV 분석용 보조 도구. 기본 자동 모드에서는 불필요 |
| toss_readonly.py | 토스 인증·종목 조회를 확인하는 보조 도구 |
| live_config.json / etf_config.json | 단일 종목 / ETF 실전 설정 |
| test_*.py / gui_smoke.py | 로직 자동 테스트 / 주문 없는 GUI 기능 점검 |
| make_manual.py | 사용 매뉴얼 DOCX 생성 |

requirements.txt는 자동 수집용 pykrx==1.2.9를 지정합니다. toss-openapi.json은 구현 때 참고한 토스 명세 사본이며 비밀키 파일이 아닙니다. input_templates는 수동 분석용 빈 양식입니다.

## 5. 처음 개발 환경 만들기

Windows에 Python 3.10 이상을 설치합니다. 설치 시 Python을 PATH에 추가하는 옵션을 확인합니다. 프로젝트 폴더에서 PowerShell을 열고 아래 명령을 한 줄씩 실행합니다. [공식 Python Windows 안내](https://docs.python.org/3/using/windows.html)

```powershell
cd C:\Users\Administrator\Downloads\proj\GITHUB\work\KoreanStockBot
python --version
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

이미 .venv가 있으면 새로 만들 필요가 없습니다. install_auto.bat를 실행해도 설치 과정을 진행할 수 있습니다. 환경 활성화 명령 없이 .venv의 python.exe를 직접 쓰면 다른 Python 버전과 혼동하기 쉽지 않습니다.

프로그램은 사용자 쓰기 권한이 있는 폴더에 둡니다. runtime·research·reports를 실행 중 생성하므로 읽기 전용 폴더에 두지 않습니다. .venv는 다른 PC로 복사해 쓰기보다 해당 PC에서 다시 생성합니다.

## 6. 실행 방법과 문법 검사

```powershell
# 모의매매 GUI
.venv\Scripts\python.exe -X utf8 app.py --mode paper
# ETF GUI: 창만 열며 주문은 시작하지 않음
.venv\Scripts\python.exe -X utf8 app.py --mode etf
# 단일 종목 GUI
.venv\Scripts\python.exe -X utf8 app.py --mode stock
# 전체 자동 테스트: 실계좌 주문 없음
.venv\Scripts\python.exe -X utf8 -m unittest -v
# GUI 버튼 동작 검사: 인증·네트워크·주문 사용 안 함
.venv\Scripts\python.exe -X utf8 gui_smoke.py
# 대표 실행 모듈 문법 검사
.venv\Scripts\python.exe -m py_compile app.py live_gui.py live.py broker.py
```

Python은 일반적인 사용에 EXE 변환이 필요하지 않습니다. py_compile은 문법을 확인하고 __pycache__에 바이트코드를 만들지만 단독 실행 EXE를 만들지는 않습니다. 문법 검사 성공만으로 API 연결·매매 로직·화면 배치가 모두 정상이라는 뜻도 아닙니다.

GUI의 인증·계좌 설정 → 계좌 조회 → 암호화 저장 → 읽기 전용 점검으로 연결을 확인합니다. 실전 시작 버튼은 실제 주문 확인창을 거칩니다. ETF와 단일 종목을 같은 폴더에서 동시에 운용하지 않습니다.

## 7. Windows EXE 빌드

현재 구현은 `release_entry.py`와 `KoreanStockBot.spec`을 사용합니다. 하나의 공통 라이브러리 폴더를 공유하는 다섯 EXE를 생성합니다.

- KoreanStockBotETF.exe: ETF GUI
- KoreanStockBotStock.exe: 단일 종목 GUI
- KoreanStockBotPaper.exe: 모의 GUI
- trader.exe: GUI가 호출하는 거래 엔진
- research.exe: 거래 엔진이 호출하는 ETF 자료 수집기

`app_paths.py`는 소스 실행에서는 프로젝트 폴더, EXE에서는 실행 파일 폴더를 설정·장부 공통 경로로 선택합니다. 소스에서는 Python + .py, 배포에서는 전용 작업 EXE를 호출합니다. 거래·수집기에는 콘솔 출력을 유지하고 GUI가 숨김 실행하여 상태 파이프를 읽습니다.

### 빌드

프로젝트 폴더의 PowerShell에서 실행합니다.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -X utf8 -m unittest -v
powershell -NoProfile -ExecutionPolicy Bypass -File build_release.ps1
```

`Release/KoreanStockBot/`에 결과가 생성됩니다. 기존 배포 폴더에 runtime 또는 research가 있으면 덮어쓰지 않고 중단합니다. 운용 중인 배포 폴더를 빌드 출력 위치로 사용하지 마세요. 새 체크아웃에서 빌드하세요.

### 오프라인 검증

```powershell
Release\KoreanStockBot\trader.exe --self-test
Release\KoreanStockBot\research.exe --self-test
Release\KoreanStockBot\trader.exe --gui-smoke
```

인증정보 읽기·API 호출·주문 없이 패키지 의존성, 암호화 왕복, 모의 계산, 세 GUI의 그래프·달력 동작을 확인합니다. 실제 인증을 사용하는 KRX 수집과 토스 체결의 검증을 대신하지 않습니다.

### 전달·업데이트

EXE만 분리하지 말고 `_internal`, 설정, 보조 EXE를 포함한 폴더 전체를 전달합니다. 개인 runtime·캐시·키는 배포물에 포함하지 않습니다. 기존 계좌를 계속 운용할 때는 거래 중지·주문 확인 후 기존 설정과 장부를 보존하는 이전이 필요합니다. 다른 폴더에서 같은 계좌 봇을 동시에 실행하지 않습니다.

PyInstaller는 파이썬 환경과 의존성을 묶는 배포 도구이며 소스코드 보호나 수익성을 보장하지 않습니다. 코드 서명은 적용하지 않았습니다. Windows 64비트에서 빌드하며 다른 운영체제용 EXE는 아닙니다.


## 8. 설정값을 읽는 방법

| 설정 키 | 현재 ETF 값 | 의미 |
|---|---|---|
| capital | 30000 | 봇이 관리할 원금 |
| allocation | 0.3 | 평가자산의 최대 30%를 투자 예산으로 사용 |
| max_order_won | 9000 | 1회 매수 상한 |
| fast / slow | 5 / 20 | 추세 판단 이동평균 기간 |
| stop_loss / take_profit | 0.03 / 0.10 | 3% 손절 신호 / 10% 익절 목표 |
| daily_loss_limit / max_drawdown | 0.02 / 0.10 | 일 손실·최대 낙폭 중단 기준 |
| daily_target / weekly_target / monthly_target | 각각 0.10 | 기간별 목표 도달 후 신규 진입 중단 |
| poll_seconds | 30 | 점검 사이 대기 시간. API 처리 시간이 추가됨 |
| cancel_after_seconds | 120 | 미체결 취소 판단 기준 |
| auto_research | true | ETF 자료 자동 갱신 |

비율 0.10은 10%입니다. 10을 입력하면 1,000%가 되므로 사용하지 않습니다. live.py의 load_config가 허용 범위를 검사합니다. GUI의 모의 설정은 실전 JSON과 별개이며 모의 기본 익절은 6%입니다.

실전 장부는 계좌 선택값과 설정 전체를 해시한 binding으로 연결합니다. 이미 장부가 있는 상태에서 설정을 바꾸면 시작이 거부될 수 있습니다. 오류를 없애려고 장부를 삭제하면 안 됩니다. 기존 주문·보유를 정산하고 마이그레이션을 설계해야 합니다.

## 9. 데이터 수집과 매매 판단

KRX에서 이름·기초지수에 코스닥/KOSDAQ이 명시된 ETF를 찾고 총순자산으로 상위 최대 20개를 선정합니다. 순위 확정 후 국내 주식 실물형 1배 상품만 허용합니다. 레버리지나 구조 불명 상품이 빠져도 21위 이하로 채우지 않습니다.

DART 기업코드를 편입 종목과 연결하고 재무 점수를 계산합니다. ETF 비중 60% 이상에서 자료가 확인되어야 하며 가중평균 점수 0.6 이상을 요구합니다. 뉴스는 최근 기사 제목·요약의 관련성과 위험 단어를 확인하는 규칙 분석입니다. 기사 전문을 이해하는 AI 분석이 아닙니다.

자동 수집 성공 후 약 1시간 뒤 갱신, 실패 후 약 5분 뒤 재시도하며 작업은 최대 30분입니다. 새 매수는 직전 영업일 자료이면서 생성 후 2시간 이내인 완성된 분석을 요구합니다. 수집 실패는 기존 보유의 가격 기반 손절·익절 판단을 중단시키는 신호는 아니지만 API 장애로 주문할 수 없는 경우는 있습니다.

매수 예산은 봇 현금·계좌 원화 현금 주문 가능 금액·1회 한도·평가자산×투자 비중 중 가장 작은 값입니다. 비용 여유분을 빼고 정수 수량을 계산합니다. 신용·대출·소수점 매수 기능은 없습니다.

## 10. 주문과 장부에서 지켜야 할 규칙

주문 전 고유 clientOrderId와 주문 의도를 저장합니다. 주문 전송 후 응답이 사라지면 실제로 접수되었을 수도 있으므로 자동 재전송하지 않습니다. 주문 내역 대조와 기존 주문 ID 연결 절차가 필요합니다.

체결 조회는 누적 체결량을 받습니다. 이미 반영한 수량을 빼고 새로 늘어난 만큼만 장부에 반영하므로 재시작 후 같은 체결을 두 번 계산하지 않습니다. 다른 기기·수동 매매로 잔고가 바뀌면 장부 불일치로 중단합니다.

Store.save는 임시 파일에 기록·flush·fsync 후 os.replace로 교체합니다. 여러 프로세스가 같은 주문 장부를 동시에 수정하지 않도록 OS 파일 잠금을 사용합니다. 장부는 단순 화면 캐시가 아니라 주문 중복과 복구를 위한 기록입니다.

중지 요청은 STOP 파일로 전달됩니다. 보유 종목은 유지하며 미체결을 취소하고 확인합니다. 창을 강제 종료하거나 인터넷이 끊기면 이미 증권사에 접수된 주문은 남을 수 있습니다.

## 11. GUI와 수익률 계산을 수정하려면

app.py의 colors와 ttk.Style은 색상·글꼴을 담당합니다. 그래프는 Tkinter Canvas에 직접 그립니다. 수익은 빨강, 손실은 파랑이며 차트는 주가 캔들이 아닌 누적 수익률 선 그래프입니다.

return_series는 일·주·월·연·전체·직접 기간에 맞춰 데이터를 고릅니다. 주는 월요일 시작, 기간 시작 직전 관측액을 기준으로 계산합니다. 달력은 Python calendar 모듈로 만들며 키보드 입력과 날짜 선택이 같은 날짜 변수를 사용합니다.

실전 observe는 날짜별 마지막 평가액과 시각을 장부에 저장합니다. GUI는 이 기록을 읽으므로 장외에는 새 그래프 점이 없을 수 있습니다. 기록 기능 이전의 과거 데이터를 복원하지 않습니다. 카드 누적 수익률은 설정 원금 기준, 선택 기간 그래프는 해당 기간 기준입니다.

| 바꾸고 싶은 내용 | 우선 볼 위치 |
|---|---|
| 배경·글자·버튼 색상 | app.py의 colors, style.configure |
| 그래프·기간·달력 | app.py의 draw_return, return_series, pick_date |
| 인증 화면·실전 버튼 | live_gui.py의 settings, start, stop, close |
| 매수 예산·중복 주문 방지 | live.py의 step, submit, reconcile 관련 코드 |
| ETF 선정·재무·뉴스 기준 | etf_live.py, etf_research.py |
| API URL·응답 형식 | broker.py와 toss-openapi.json |
| 자료 갱신 주기 | auto_research.py의 tick |

## 12. 테스트·오류 해결·Git 관리

test_engine은 모의 체결, test_broker는 주문 API 차단, test_live는 주문·재시작·손실 제한, test_etf는 순위·재무·뉴스, test_auto는 자동 수집·프로세스·암호화, test_chart는 기간 수익률, test_live_gui는 장부 관측 기록을 검사합니다. gui_smoke는 세 GUI에서 그래프·직접 기간·달력 선택을 점검합니다.

수정 → 관련 테스트 → 전체 테스트 → GUI 점검 → 읽기 전용 연결 순서로 검증합니다. 읽기 전용은 자동 주문을 검증하지 않으므로 실제 체결 검증 완료로 보고하지 않습니다.

| 문제 | 확인할 곳 |
|---|---|
| ModuleNotFoundError | 올바른 .venv Python인지, requirements 설치 여부 |
| 403 / IP 거부 | 토스 허용 공인 IP. 연결 변경만으로 키 재발급은 불필요 |
| SETUP_REQUIRED | 인증정보 누락 |
| COLLECTION_FAILED | research/auto_status.json, KRX 로그인·DART 점검·뉴스 권한 |
| Another bot process holds the lock | 다른 창이나 콘솔에서 봇 실행 여부 |
| Account/config changed | 설정과 기존 장부의 binding 불일치. 장부 삭제 금지 |
| UNKNOWN order outcome | 토스 실제 주문 내역 대조. 반복 주문 금지 |

Git에는 코드·테스트·설정 템플릿·문서를 올립니다. .venv, runtime, research, reports, .env, STOP 등은 .gitignore로 제외합니다. 암호화 파일도 공유하지 않습니다. 같은 저장소에 다른 프로젝트가 있으므로 git add . 대신 대상 폴더를 지정합니다.

```powershell
# 상위 work 저장소에서 변경 내용을 검토한 뒤 실행
git status --short -- KoreanStockBot
git add -- KoreanStockBot
git diff --cached --stat
git commit -m "Update KoreanStockBot documentation"
git push origin main
```

이 문서 생성만으로 자동 푸시하지 않습니다. 커밋·푸시는 변경 내용과 대상 브랜치를 확인한 뒤 실행합니다.

## 13. 소스코드 읽기 예제

다음 부록은 작성 시점 실제 소스에서 추출합니다. 파일명과 함수명을 기준으로 전체 파일을 열어 앞뒤 흐름도 함께 확인하세요. 보안키와 계좌 기록은 포함하지 않습니다.

## 14. 공식 참고 문서

- Python Windows: https://docs.python.org/3/using/windows.html
- Python 문법 컴파일: https://docs.python.org/3/library/py_compile.html
- PyInstaller 사용법: https://pyinstaller.org/en/stable/usage.html
- PyInstaller 경로·실행 파일: https://pyinstaller.org/en/stable/runtime-information.html
- 토스 인증·허용 IP: https://developers.tossinvest.com/docs/auth
- pykrx: https://github.com/sharebook-kr/pykrx
- OpenDART: https://opendart.fss.or.kr/
- NAVER API HUB 뉴스: https://api.ncloud-docs.com/docs/naver-api-hub-search-news
- NAVER API HUB 가입·앱 등록: https://guide.ncloud-docs.com/docs/apihub-application

뉴스 연동은 https://naverapihub.apigw.ntruss.com/search/v1/news 에 format=json으로 요청합니다. 인증 헤더는 X-NCP-APIGW-API-KEY-ID와 X-NCP-APIGW-API-KEY입니다. 로컬 설정 이름 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET은 유지하되 API HUB에서 발급한 값을 입력합니다. 기존 API로 자동 전환하지 않습니다. 뉴스 캐시는 시간 단위이며 새 URL로 기존 캐시와 분리됩니다. test_news_hub.py에서 요청 형식·시간별 캐시·오류 응답 저장 방지를 검사합니다.

각 문서는 외부 서비스의 변경에 따라 달라질 수 있습니다. API 변경 시 최신 명세와 코드의 요청·응답 필드를 대조하세요.
