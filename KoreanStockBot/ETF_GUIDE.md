# 코스닥 ETF 자동 수집·분석·주문

**현재 start_etf.bat는 GUI를 엽니다.** 인증·계좌 설정 → 읽기 전용 점검 → 실전 시작 버튼을 사용하세요. 아래 Enter/LIVE 설명은 기존 `python launch_live.py --etf` 콘솔 방식입니다. 현재 사용법은 [GUI_GUIDE.md](GUI_GUIDE.md)를 확인하세요.

CSV, 종목 목록, 재무제표, 기사를 직접 준비하지 않습니다. 최초 인증 설정 후 프로그램이 자료를 수집하고 갱신하여 매매를 판단합니다. 실제 인증을 통한 최신 자료 수집과 계좌 체결은 아직 검증하지 못했습니다. 10%는 목표이며 수익을 보장하지 않습니다.

## 처음 실행

1. Python 3.10 이상이 설치된 Windows에서 `install_auto.bat`를 실행합니다.
2. 아래 서비스에 가입하고 인증정보를 발급합니다.
3. `start_etf.bat`를 실행해 인증정보와 토스 계좌 선택값을 입력합니다. 종목코드나 CSV는 필요 없습니다.
4. Windows 암호화 저장을 선택하면 같은 Windows 사용자로 다음 실행부터 재사용합니다.
5. Enter는 주문 없는 연속 점검입니다. 실제 주문은 실행 모드에 `LIVE`를 입력합니다.

| 서비스 | 최초 준비 | 입력값 |
|---|---|---|
| [토스증권 Open API](https://home.tossinvest.com/ko/open-api) | 웹 설정 → Open API 신청, 키 발급, 공인 IP 등록 | Client ID, Client Secret, 조회된 accountSeq |
| [KRX](https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd) | 회원가입 및 로그인 확인 | KRX_ID, KRX_PW |
| [OpenDART](https://opendart.fss.or.kr/) | 인증키 신청 | DART_API_KEY |
| [네이버 개발자센터](https://developers.naver.com/docs/serviceapi/search/news/news.md) | 애플리케이션 등록, 검색 API 설정 | NAVER_CLIENT_ID, NAVER_CLIENT_SECRET |

가입·본인인증·권한 부여는 프로그램이 대신할 수 없습니다. 키는 채팅이나 소스코드에 넣지 말고 실행 콘솔에 입력합니다. 선택적 저장 파일 `runtime/credentials.dpapi`는 Windows DPAPI로 암호화합니다. PC와 프로그램이 켜져 있고 인터넷에 연결되어 있어야 합니다.

## 자동 처리

- 토스 공식 시장 캘린더로 직전 영업일을 확인합니다.
- KRX 전체 ETF 중 이름 또는 기초지수에 코스닥/KOSDAQ이 명시된 상품을 총순자산(원) 내림차순으로 최대 20개 선정합니다. 주당 NAV·시가총액으로 대체하지 않습니다. 동률은 종목코드순입니다.
- 순위 확정 후 국내 주식 실물형 1배만 허용합니다. 레버리지·인버스·파생·합성·구조 불명 상품은 매수하지 않으며 21위 이하로 채우지 않습니다.
- 구성종목·편입 비중을 수집하고 DART 기업코드를 연결합니다. 현금이나 미확인 비중을 다른 기업에 재배분하지 않습니다.
- 기업 재무제표와 ETF·주요 편입 기업 뉴스를 자동 조회합니다. 조건을 통과하고 예산으로 살 수 있는 ETF 하나를 선택합니다. 동시 보유는 최대 1개입니다.

상품명·기초지수에 코스닥이 없는 테마 ETF는 포함하지 않습니다. KRX 수집에는 로그인 정보를 사용하는 외부 라이브러리 [pykrx](https://github.com/sharebook-kr/pykrx) 1.2.9를 이용합니다. KRX 사이트나 접근 정책 변경 시 수정이 필요할 수 있습니다.

수집은 별도 프로세스에서 실행하며 토스 인증 환경변수를 전달하지 않습니다. 성공 후 약 1시간 간격으로 갱신하고 실패 시 약 5분 뒤 재시도합니다. 작업 한 번은 최대 30분이며 프로그램 종료 시 함께 중단합니다. 최초 수집은 편입 기업 수에 따라 오래 걸릴 수 있습니다.

신규 매수에는 직전 영업일 기준이고 생성 후 2시간 이내인 완성된 분석만 사용합니다. 편입 자료 누락 ETF는 순위는 유지하되 매수를 보류합니다. 분석 장애 시에도 기존 보유분의 가격 기반 손절·익절 판단을 유지하지만 증권 API 장애나 거래 불가 상황에서는 주문할 수 없습니다.

## 판단 규칙과 목표

편입 기업별 매출·영업이익·순이익·영업현금흐름 양수, 자기자본/자산 30% 이상 여부를 점수화합니다. 전체 편입 비중의 60% 이상을 확인하고, 확인된 비중의 가중평균 점수가 0.6 이상이어야 매수 후보입니다. 연결 재무제표를 우선하며 자료가 없을 때 별도 재무제표를 사용합니다. 최신 보고서의 지표가 누락되었다고 오래된 좋은 보고서로 대체하지 않습니다.

뉴스는 ETF명과 편입 비중 상위 3개 기업명으로 검색한 최근 7일 제목·요약입니다. 중복을 제거하고 횡령·회계부정·거래정지 등 위험 단어를 검사합니다. 위험 단어가 있거나 관련 뉴스가 없으면 신규 매수를 보류합니다. 기사 전문을 이해하는 AI가 아닌 규칙 기반 분석이며 문맥을 오판할 수 있습니다.

- 후보는 재무점수 우선, 동점이면 순자산 순위 우선입니다.
- 완성된 일봉 5일 평균이 20일 평균보다 높아야 진입합니다. 시세·호가·잔고·수량 조건도 확인합니다.
- 비용을 고려한 개별 보유분 추정 수익률 10%에서 지정가 익절을 시도합니다.
- 손절 3%, 일 손실 중단 2%, 최대 낙폭 중단 10%를 적용합니다. 손실 상한이나 체결 보장은 아닙니다.
- 봇 평가자산의 일·ISO 주·월 목표 각각 10% 중 하나라도 도달하면 청산을 시도하고 해당 기간 신규 매수를 중단합니다. 월 목표 도달 시 다음 달까지 기다릴 수 있습니다.
- 재무점수 0.4 미만과 위험 뉴스가 동시에 확인되거나 가격 추세가 하락하면 청산 신호입니다.
- 수익·손실은 다음 투자 가능 금액에 반영합니다. 기본 원금 3만원, 투자 비중 30%, 1회 매수 최대 9천원 상한은 유지합니다. 비용 포함 1주를 살 수 없으면 거래하지 않습니다.

전략 수익성은 검증되지 않았습니다. 일·주·월 10%를 꾸준히 달성하도록 보장하는 기능은 없습니다.

## 결과와 중지

| 파일 | 내용 |
|---|---|
| `research/auto_status.json` | 수집 진행·완료·실패 |
| `research/auto_latest.json` | 완성된 자동 분석과 출처·판단 근거 |
| `research/latest_summary.csv` | 최근 순위와 매수 보류 사유 |
| `research/automatic_inputs/` | 프로그램이 생성한 내부 자료; 작성 불필요 |
| `research/cache/` | 뉴스 시간 단위, 재무·KRX 일 단위 캐시 |
| `runtime/etf_live_state.json` | 실제 주문·보유 상태; 삭제·초기화 금지 |

`stop_live.bat`는 다음 점검에서 미체결 취소를 요청하고 종료합니다. **보유 ETF는 유지합니다.** 창을 닫으면 프로세스만 종료되므로 기존 주문·보유분은 토스에서 확인해야 합니다. 복구와 계좌 검사 동작은 [LIVE_GUIDE.md](LIVE_GUIDE.md)를 따릅니다. 기존 실행 상태와 설정이 불일치하더라도 상태 파일을 지워 해결하지 마세요.

저장된 인증정보 또는 로컬 환경변수로 CLI를 실행할 수 있습니다.

```powershell
.venv\Scripts\python.exe live.py --etf          # 자동 수집 + 연속 읽기 전용
.venv\Scripts\python.exe live.py --etf --live   # 자동 수집 + 실제 주문
.venv\Scripts\python.exe live.py --etf --once   # 기존 분석만 1회 점검; 새 수집 없음
.venv\Scripts\python.exe -X utf8 -m unittest -v
```

기존 `prepare_etf.bat`와 입력 템플릿은 수동 분석 보조 도구입니다. 자동 모드에서는 필요 없으며 기본 주문 프로그램은 `research/auto_latest.json`을 읽습니다.

명세: [DART 기업코드](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018), [DART 재무제표](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020), [네이버 뉴스](https://developers.naver.com/docs/serviceapi/search/news/news.md), [토스 OpenAPI](https://openapi.tossinvest.com/openapi-docs/latest/openapi.json).
