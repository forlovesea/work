KoreanStockBot Windows EXE

뉴스 연동: NAVER API HUB (네이버 클라우드) 방식으로 변경되었습니다.
API HUB Application에서 NAVER Search의 News를 선택하고 발급한 Client ID/Secret을
GUI의 인증·계좌 설정에 입력하여 암호화 저장하세요. 기존 개발자센터 키는 교체해야 합니다.
사용량·요금·한도는 네이버 클라우드 콘솔에서 확인합니다.

실행 파일
  KoreanStockBotETF.exe   : ETF 자동매매 GUI
  KoreanStockBotStock.exe : 단일 종목 자동매매 GUI
  KoreanStockBotPaper.exe : 모의매매 GUI

trader.exe, research.exe, _internal 폴더는 필수 구성요소입니다.
EXE 하나만 복사하지 말고 KoreanStockBot 폴더 전체를 옮기세요.
Python을 별도로 설치하지 않고 실행하도록 묶은 Windows 64비트 배포입니다.
쓰기 가능한 폴더에서 사용하세요. 처음 실행은 인증·계좌 설정 → 읽기 전용 점검입니다.
실전 시작 버튼과 확인창 승인 전에는 실제 주문하지 않습니다.
API 권한·허용 IP 등록은 필요하며 실계좌 체결·수익성은 검증되지 않았습니다.
공인 IP 변경만으로 API 키를 재발급할 필요는 없습니다.

개인 인증정보·계좌 장부는 배포물에 포함하지 않습니다.
기존 실행 폴더에 보유·주문 기록이 있다면 새 폴더에서 곧바로 실전 시작하지 마세요.
기존 봇 종료와 주문 확인 후 같은 계좌·설정·runtime 장부를 함께 이전해야 합니다.
DPAPI 인증정보는 같은 Windows 사용자 환경에서만 재사용 가능합니다.
Release와 소스 폴더의 봇을 동시에 실행하지 마세요(폴더별 잠금은 서로 다릅니다).
중지는 보유 종목 매도가 아닙니다. 인터넷 단절·강제 종료 시 토스에서 직접 확인하세요.

EXE는 자체 서명되지 않았으며 Windows 보안 경고가 나올 수 있습니다.
출처와 해시를 확인하고 조직 보안 정책을 따르세요. 보안 프로그램을 끄지 마세요.
