"""Build a Korean Word manual using standard-library OOXML only."""
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
parts = []

def p(text='', style='Normal'):
    content='<w:br/>'.join(f'<w:t xml:space="preserve">{escape(line)}</w:t>' for line in text.split('\n'))
    parts.append(f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r>{content}</w:r></w:p>')

def title(number, text):
    if parts:
        parts.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    p(f'KOREAN STOCK BOT  /  {number:02d}', 'Subtitle')
    p(text, 'Title')

def table(headers, rows):
    widths = [2400, 6900] if len(headers)==2 else [2200, 3000, 4100]
    xml='<w:tbl><w:tblPr><w:tblW w:w="9300" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblBorders>'
    for side in ('top','left','bottom','right','insideH','insideV'):
        xml+=f'<w:{side} w:val="single" w:sz="4" w:color="DCE5EE"/>'
    xml+='</w:tblBorders><w:tblCellMar><w:top w:w="100" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:bottom w:w="100" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>'
    xml+=''.join(f'<w:gridCol w:w="{v}"/>' for v in widths)+'</w:tblGrid>'
    for i,row in enumerate([headers]+rows):
        xml+='<w:tr><w:trPr><w:cantSplit/>'+('<w:tblHeader/>' if i==0 else '')+'</w:trPr>'
        for width,text in zip(widths,row):
            bg='176B63' if i==0 else ('F1F5F9' if i%2 else 'FFFFFF')
            xml+=f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/><w:shd w:fill="{bg}"/></w:tcPr><w:p><w:pPr><w:spacing w:after="40"/></w:pPr><w:r><w:rPr><w:color w:val="'+('FFFFFF' if i==0 else '172B4D')+'"/><w:sz w:val="20"/></w:rPr><w:t>'+escape(text)+'</w:t></w:r></w:p></w:tc>'
        xml+='</w:tr>'
    parts.append(xml+'</w:tbl>')
    p()

title(1,'코스닥 ETF 자동매매\n처음 사용하는 분을 위한 매뉴얼')
p('사전 준비 · 인증키 발급 · 실행 · 그래프 · 중지와 문제 해결','Subtitle')
p('이 문서는 현재 KoreanStockBot 폴더에 있는 프로그램을 기준으로 작성했습니다. 별도의 종목 목록이나 CSV를 준비하지 않아도 실전 ETF 모드에서 자료를 자동 수집합니다.')
p('가장 먼저 알아둘 3가지','Heading1')
p('① 세 실행 파일 모두 GUI입니다. start.bat는 모의매매, start_etf.bat는 ETF, start_live.bat는 단일 종목입니다. 실제 주문은 실전 시작 버튼과 확인창 승인을 거쳐 시작합니다.')
p('② 실제 계좌 접속·주문·체결은 아직 검증하지 않았습니다. 첫날에는 읽기 전용 점검부터 진행하고 첫 주문을 토스 앱에서 직접 확인하세요.')
p('③ 일·주·월 10%는 목표입니다. 수익이나 손실 제한 가격에서의 체결을 보장하지 않습니다. 인터넷이 끊기거나 PC가 꺼지면 손절·익절도 실행할 수 없습니다.','Callout')
table(['읽을 순서','내용'],[
 ('02 / 준비물','PC·계좌·테더링 준비'),('03 / 서비스 가입','토스·KRX·DART·네이버 인증 발급'),
 ('04 / 첫 실행','설치 → 인증 입력 → 주문 없는 점검'),('05 / 실제 매매','실전 시작과 매일 확인할 사항'),
 ('06 / 화면 사용','모의매매 GUI와 수익률 그래프'),('07 / 종료·오류','중지, 재시작, 통신 장애 대처'),('08 / 참고','매매 규칙·파일 위치·공식 링크'),('09 / 접속 환경 변경','집 공유기·테더링 전환과 허용 IP 관리')])
p('작성 기준: 2026-10-11 · 현재 코드 및 공식 안내 확인 기준. 서비스 메뉴·이용 조건은 변경될 수 있습니다.','Small')

title(2,'사전 준비물과 테더링')
table(['준비물','확인할 내용'],[
 ('Windows PC','Python 3.10 이상, 전원 연결, 충분한 저장 공간'),
 ('프로그램 폴더','KoreanStockBot 전체 폴더를 같은 위치에 유지'),
 ('토스증권 계좌','본인 계좌와 앱 로그인, 원화 현금 주문 가능 금액 확인'),
 ('서비스 인증','토스 API 키 2개 / KRX 계정 / DART 키 / 네이버 키 2개'),
 ('인터넷','휴대폰 테더링과 데이터 잔량, 충전 및 발열 확인'),
 ('문서 열기','Microsoft Word 또는 DOCX를 읽는 문서 프로그램')])
p('테더링은 이 순서로 준비하세요','Heading1')
for s in [
 '1. 거래할 PC를 휴대폰 테더링에 연결합니다. Wi-Fi 또는 USB 방식 모두 가능합니다.',
 '2. 그 PC의 브라우저에서 “내 IP 확인”을 검색해 외부에서 보이는 공인 IP를 확인합니다. 192.168… 같은 내부 주소를 등록하지 않습니다.',
 '3. 토스증권 웹의 설정 → Open API → 허용 IP 관리에 해당 공인 IP를 등록합니다. 공식 안내: 참고 페이지 [1].',
 '4. 테더링을 껐다 켜거나 통신망이 바뀌면 공인 IP가 달라질 수 있습니다. 다시 연결한 뒤에는 IP를 재확인합니다. USB 테더링도 고정 IP가 아닙니다.',
 '5. PC 절전·최대절전·덮개 닫힘에 따른 절전을 해제합니다. 화면만 꺼지는 것은 괜찮습니다. 장중 재부팅과 네트워크 전환을 피하세요.']: p(s)
p('계좌도 미리 확인하세요','Heading1')
p('기본 원금은 30,000원입니다. 최초 현금 주문 가능 금액이 이보다 적으면 실행이 중단됩니다. 기존 보유 종목·미체결·조건주문이 있으면 시작이 거부될 수 있습니다. 앱에서 확인하되, 프로그램 실행을 위해 기존 자산을 무조건 매도하지는 마세요.')
p('운용 중 같은 계좌에서 수동 매매나 다른 봇을 함께 사용하지 않습니다. 원화 현금 범위에서만 매수하며, 기본 1회 매수 상한은 9,000원입니다.','Callout')

title(3,'서비스 가입과 인증정보 발급')
p('A. 토스증권 — 주문과 계좌 조회','Heading1')
p('토스증권 웹에 로그인 → 설정 → Open API에서 신청과 키 발급을 진행합니다. Client ID와 Client Secret을 확인하고 실제 사용할 PC의 공인 IP를 등록합니다. 메뉴가 없으면 본인 계정의 이용 가능 여부를 공식 안내에서 확인하세요. [1]')
p('B. KRX — ETF 순자산과 편입 종목','Heading1')
p('KRX Data Marketplace에서 회원가입하고 정상 로그인되는지 확인합니다. KRX_ID는 이 사이트의 로그인 아이디이며 KRX_PW는 비밀번호입니다. 토스 계정이나 별도 API 키가 아닙니다. 현재 수집 라이브러리는 KRX 로그인을 사용합니다. [2, 6]')
p('C. OpenDART — 기업 재무제표','Heading1')
p('OpenDART → 인증키 신청/관리 → 인증키 신청에서 개인 이용자로 신청합니다. 화면의 인증 절차를 진행하고 사용 목적은 “개인 투자 분석용 재무제표 조회”처럼 실제 용도를 적습니다. 인증키 관리에서 발급 상태와 키를 확인합니다. 이 값이 DART_API_KEY입니다. [3]')
p('작성 시점에 DART 신청 페이지는 점검 안내로 연결되었습니다. 신청·키 관리와 고유번호 API 등이 중단 대상으로 안내되어 있습니다. 신청 전에 현재 공지를 확인하세요. 같은 점검이 계속되면 최초 기업코드 수집도 실패할 수 있습니다. [4]','Callout')
p('D. 네이버 — 관련 뉴스 검색','Heading1')
p('네이버 클라우드 가입·로그인 → 콘솔 → All Services → Application Services → NAVER API HUB에서 이용 신청합니다. Application → Application 등록에서 NAVER Search의 News(뉴스)를 선택하고 이름은 KoreanStockBot처럼 영문으로 입력합니다. 앱 선택 → API 관리 → 인증 정보에서 Client ID와 Client Secret을 확인합니다. [5]')
p('기존 개발자센터에서는 2026년 7월 31일부터 검색 API 신규 신청을 받지 않습니다. WEB 설정이나 localhost 등록 대신 API HUB 신청 절차를 사용합니다. 이용 요금·사용량 한도·알림을 확인하세요. 기존 개발자센터 키는 새 키로 교체해야 합니다.')
p('인증값은 프로그램 실행창에만 입력하세요. 채팅·소스코드·공유 문서에 실제 키를 적지 않습니다. 네이버 API 키는 네이버 로그인 비밀번호와 다릅니다.','Small')

title(4,'처음 설치하고 주문 없이 점검하기')
p('1단계 / 설치','Heading1')
p('파일 탐색기에서 KoreanStockBot 폴더를 열고 install_auto.bat를 더블클릭합니다. 설치가 끝나 “Ready. Run start_etf.bat.”가 보이면 안내에 따라 창을 닫습니다. 처음 한 번 필요하며 인터넷 연결이 있어야 합니다.')
p('“python을 찾을 수 없음”이 나오면 Python 설치와 PATH 등록을 확인합니다. 설치 파일이 실패했다고 나오는 경우 인터넷 연결을 복구한 뒤 다시 실행합니다. [7]')
p('2단계 / 인증정보 입력','Heading1')
p('start_etf.bat를 열고 인증·계좌 설정 버튼을 누릅니다. 아래 값을 입력하고 계좌 조회 후 목록에서 사용할 계좌를 선택합니다. 계좌가 하나면 자동 선택되고, 여러 개면 직접 선택합니다. 토스 인증정보 변경 시 다시 조회해야 합니다. 저장한 인증값은 자동으로 불러오며 화면에서는 가려집니다. 단일 종목은 start_live.bat에서 종목코드도 입력합니다.')
table(['실행창 항목','입력할 값'],[
 ('Client ID / Client Secret','토스증권에서 발급한 두 값'),('KRX_ID / KRX_PW','KRX 로그인 아이디와 비밀번호'),
 ('DART_API_KEY','OpenDART 인증키'),('NAVER_CLIENT_ID / NAVER_CLIENT_SECRET','네이버에 등록한 앱의 두 값'),
 ('accountSeq','화면에 조회된 계좌 선택값 중 사용할 값. 계좌번호가 아닙니다.')])
p('암호화 저장을 누르면 같은 Windows 사용자로 다음 실행부터 인증정보를 재사용합니다. 실제 키를 문서나 채팅에 넣지 마세요.')
p('3단계 / 읽기 전용 점검','Heading1')
p('키·비밀번호 입력칸 옆 눈 모양의 보기 / 숨기기 버튼으로 값을 확인할 수 있습니다. 창을 다시 열면 숨김 상태로 돌아갑니다. 앞뒤 공백·탭·줄바꿈은 조회와 저장 시 자동으로 제거됩니다. 값 내부의 문자는 유지됩니다.')
p('파일로 설정하기: 설정 템플릿 생성 → JSON을 메모장으로 열어 credentials의 빈 값에 키 입력 → 템플릿 암호화 변환으로 .ksbkey 저장 → 설정 파일 불러오기 → 계좌 조회·선택 → 암호화 저장 순서입니다. 계좌 선택값은 템플릿에서 비워 둬도 됩니다. symbol은 단일 종목 코드이며 ETF에서는 비워 둡니다. 형식·항목 이름을 변경하지 마세요. 따옴표·역슬래시는 JSON 이스케이프 규칙이 필요합니다.')
p('암호화 파일은 같은 PC의 동일 Windows 사용자에서 복호화됩니다. 같은 사용자 권한의 프로그램까지 차단하지는 않습니다. 암호화 검증 후 평문 원본 삭제 여부를 묻습니다. 삭제하지 않은 원본과 클라우드·백업 사본에는 키가 남으므로 별도로 관리하세요. 불러오기만으로 저장하거나 실전 주문을 시작하지 않습니다.')
p('읽기 전용 점검 버튼을 누르면 실제 주문 없이 연속 점검합니다. 화면에 읽기 전용 상태가 표시됩니다. 이 모드는 계좌 조회이며 가상 체결을 만드는 모의매매와 다릅니다.')
p('수집 단계와 오류는 실행파일 폴더의 research/logs/collection.log에 자동 기록됩니다. 메모장으로 열면 time(한국시간), run_id(작업 ID), stage(현재 단계), START/COMPLETED/FAILED(시작/완료/실패), error_code(오류 분류), http_status(HTTP 코드)를 확인할 수 있습니다. 로그는 2MB마다 순환하며 이전 파일은 최대 5개 보관합니다. 키·비밀번호·URL·헤더·원문 오류 메시지는 기록하지 않습니다. 화면의 미요청 상태는 키 오류가 아니라 아직 해당 단계에 도달하지 않았다는 뜻이며, 앞 단계 실패인 경우 별도로 표시합니다.')
p('ETF 후보 제안은 중복된 순위 범위 대신 실제 종목 목록을 보여줍니다. 봇 중지 완료 후 창을 열면 최신 계좌·시세를 읽기 전용으로 조회합니다. 자동 수집된 재무·뉴스 자료와 추세를 검사해 통과 종목을 추천하고, 제외 종목에는 사유를 표시합니다. 추천 종목을 클릭해 선택/해제 → 선택한 종목 적용 → 실전 시작 순서로 사용하세요. 선택한 종목들 안에서 한 번에 한 종목을 운용합니다. 분석 후 5분이 지나면 다시 조회해야 적용할 수 있습니다. 실제 주문 전 조건을 재검사하며, 기존 보유분의 매도 조건은 유지합니다. 조회 실패 시 읽기 전용 점검으로 자동 자료 수집 상태를 확인하세요. 장외 시세가 오래됐으면 후보를 추천하지 않습니다.')
p('ETF 후보 없음 안내에는 관리 현금·투자 비중·주문 상한·계좌 현금매수가능 금액과 후보별 제외 사유가 표시됩니다. 재무점수와 확인 비중의 기준은 각각 60%이며, 뉴스와 추세도 확인합니다. 1주 필요 추정은 현재가 × 1.01 + 10원으로 계산합니다. 전체 후보 사유는 아래 스크롤 로그에서 확인하세요. 안내는 예산이나 조건을 자동 변경하지 않습니다.')
p('자료 수집 상태에서는 KRX·DART·NAVER의 API 성공, 캐시 사용, 오류 횟수와 기록 시각을 확인합니다. 캐시는 이번 키의 인증 성공을 검증하지 않습니다. READY는 분석 파일이 완성되었다는 뜻이며 매수 조건 통과 개수는 별도로 표시합니다. 업데이트 전 수집 이력은 상세 기록 없음으로 표시하며 다음 자동 수집부터 기록됩니다.')
p('실전 시작 후 실행 상태 영역에서 휴장 대기·매매 시작 대기·매매시간 종료·연결 실패를 확인합니다. 휴장 중 신규 매수·매도 주문은 보내지 않습니다. 다음 개장 시각은 토스 시장 캘린더로 확인하며, 마지막 상태 수신 시각과 경과 초도 표시됩니다. 응답이 오래 없으면 응답 지연으로 표시합니다. 봇은 개장 2분 후부터 마감 동시호가 2분 전까지 조건을 확인하며, 개장만으로 매수하지 않습니다.')
p('자료 수집에는 시간이 걸립니다. research 폴더의 auto_status.json을 메모장으로 열어 state가 READY인지 확인합니다. auto_latest.json은 완성된 분석이고 latest_summary.csv는 엑셀로 볼 수 있는 요약입니다. READY는 수집 성공이며, 매수 대상이 있다는 뜻은 아닙니다.')
p('중지 요청을 누르고 프로세스 종료를 확인하면 같은 창에서 실전 시작을 누를 수 있습니다. 동시에 다른 전략을 실행하지 않습니다.','Small')
p('우측 상단 프로그램 종료 버튼은 스크롤과 관계없이 표시됩니다. 누르면 진행 중인 조회 완료를 기다리고, 봇의 미체결 정리 및 정상 종료를 확인한 뒤 창을 닫습니다. 정상 중지 미확인 시 창을 유지하고 안내합니다. 보유분은 매도하지 않으며 자동 감시는 종료됩니다. 모의매매는 reports/paper_exit_시각 폴더에 결과를 자동 저장합니다. 창의 X 버튼도 같은 절차를 사용합니다.')
p('최신 계좌·시세 조회 후 후보가 없으면 후보 제안 불가 사유 팝업이 표시됩니다. 시장 상태와 실제 제외 사유별 종목 수를 보여줍니다. 오래된 시세로 제외된 경우 다음 정규장 재조회를 안내하고, 분석 자료 만료·인증 또는 접근 거부·통신 실패 등은 구분해 안내합니다. 같은 내용을 하단 로그에서도 확인할 수 있습니다.')
p('중지 요청 접수는 종료 완료가 아닙니다. 진행 중인 통신 응답 후 주문을 조회하고 미체결 정리를 확인합니다. 중지 요청 후 경과 시간이 표시되며 60초 이상이면 처리 지연 안내가 나옵니다. 정상 종료와 중지 완료 응답을 모두 확인해야 중지 완료로 표시합니다. 정상 중지 미확인 시 토스 앱에서 미체결·보유분을 확인하세요. 보유 종목은 자동 매도하지 않으며, 중지 후 자동 손절·익절 감시도 종료됩니다.')

title(5,'실제 매수·매도 시작과 매일 사용법')
p('첫 실전 시작','Heading1')
for s in [
 '1. 테더링 연결과 공인 IP 등록, 토스 앱 접속 상태를 확인합니다.',
 '2. 먼저 읽기 전용으로 최신 분석·계좌·시세 조회가 정상인지 확인합니다. 장외 표시만으로 장중 주문까지 검증된 것은 아닙니다.',
 '3. 중지 요청을 누르고 점검 프로세스 종료를 확인합니다.',
 '4. 대상, 원금, 한도를 확인하고 실전 시작 버튼과 확인창을 승인합니다.',
 '5. LIVE ORDERS ENABLED는 실제 주문이 활성화되었다는 뜻입니다. 매수 조건을 만족하면 별도 확인 없이 주문하므로 첫날에는 직접 지켜보세요.',
 '6. 첫 주문의 접수·체결 여부와 수량·금액을 토스 앱에서 확인합니다. 주문 접수와 체결은 다릅니다.']: p(s)
p('왜 바로 매수하지 않나요?','Heading1')
p('정규장 캘린더, 최신 분석, 재무·뉴스, 가격 추세, 정상 호가, 현금과 정수 수량 조건을 모두 확인합니다. 원금 3만원이어도 기본 1회 매수는 최대 9천원입니다. 비용 포함 1주를 살 수 없으면 기다립니다. 상위 20개를 모두 사는 것이 아니라 적격 ETF 1개만 보유합니다.')
p('매일 시작 전에 확인','Heading1')
p('□ 테더링과 허용 공인 IP가 일치한다.\n□ PC 절전과 자동 재부팅을 방지했다.\n□ 토스 앱에서 계좌·미체결 내역을 확인했다.\n□ 최신 분석이 있고 오류가 반복되지 않는다.\n□ 동일 프로그램이 중복 실행되지 않는다.\n□ 비상시 토스 앱에서 직접 주문을 확인할 수 있다.')
p('운용 중·종료 후 확인','Heading1')
p('GUI를 켜 두고 하단 로그에서 통신 오류·분석 실패·주문 불명확 메시지를 확인합니다. 종료 전 중지 요청 후 토스 앱의 보유분·미체결을 확인합니다. 장 마감 시 무조건 전량 매도하지 않습니다.')
p('프로그램은 로그인 상태의 PC에서 실행되는 동안만 작동합니다. 무인 서버, 휴대폰 앱 실행, 원격 알림 기능은 현재 포함하지 않습니다.','Callout')

title(6,'모의 화면과 수익률 그래프 보기')
p('start.bat는 연습용입니다. ETF·단일 종목 GUI도 같은 그래프·기간 선택·달력을 사용하며, 실전 모드에는 봇이 실제 관측한 평가자산만 표시합니다.','Callout')
p('따라 해 보기','Heading1')
for s in [
 '1. start.bat를 더블클릭합니다. 투자 전략 스튜디오가 열립니다.',
 '2. 처음에는 내장된 합성 데모 데이터를 사용합니다. 실제 ETF의 과거 성과가 아닙니다.',
 '3. 시작 금액과 투자 비중 등을 확인하고 백테스트를 누릅니다.',
 '4. 평가자산·누적 수익률·최대 낙폭·보유 수량 카드와 체결 표를 확인합니다.',
 '5. 수익률 그래프를 누르면 큰 창이 열립니다. 선 위에 마우스를 올리면 날짜별 수익률이 표시됩니다.',
 '6. 모의 재생은 일봉을 순서대로 진행하며 화면과 확대 그래프를 갱신합니다. 재생 중지는 연습 재생만 멈춥니다.']: p(s)
table(['버튼','무엇을 하나요?'],[
 ('CSV 불러오기','개인이 가진 과거 일봉으로 실험할 때만 사용. 실전 자동 수집에는 불필요'),
 ('백테스트 / 모의 재생','과거 데이터 일괄 계산 / 순차 재생'),('수익률 그래프','누적 수익률을 새 창으로 확대'),
 ('결과 저장','reports 폴더에 모의 결과 저장'),('10% 복리 계산','수익이 매번 10%라고 가정한 산술 계산. 예측이 아님')])
p('그래프 읽는 방법','Heading1')
p('가로축은 날짜, 세로축은 시작 자금 대비 누적 수익률(%)입니다. 0% 점선 위는 시작보다 평가자산이 증가한 상태이고 아래는 감소한 상태입니다. 예: 30,000원 → 33,000원이면 +10%, 27,000원이면 -10%입니다.')
p('평가자산에는 미청산 보유분도 포함됩니다. 모의 비용 가정은 반영하지만 최종 미청산 보유분의 향후 매도 비용은 차감하지 않습니다. 실전 수익은 토스 앱의 실제 체결과 잔고에서 확인하세요.')
p('모의 GUI의 설정값은 실전 etf_config.json과 별개입니다. GUI 숫자를 바꿔도 실전 매수 한도나 익절 설정은 바뀌지 않습니다.','Small')
p('실전 그래프: 일·주·월·연·전체·직접 기간을 선택합니다. 직접 기간은 키보드 또는 캘린더로 선택 후 기간 적용을 누릅니다. 일별 마지막 관측값을 표시하며, 과거 미관측 구간은 복원하지 않습니다. 카드 수익률은 설정 원금, 그래프는 선택 기간 직전 관측값 기준입니다.','Small')

title(7,'중지·재시작과 문제 해결')
p('정상적으로 중지하기','Heading1')
p('① GUI의 중지 요청 또는 stop_live.bat를 실행합니다. → ② 다음 점검에서 미체결 취소 결과를 확인할 때까지 기다립니다. → ③ 토스 앱에서 미체결과 보유분을 확인합니다. 운용 중 창 닫기는 중지 후 종료 확인창을 거칩니다.')
p('중지는 전량 매도가 아닙니다. 보유분은 남습니다. 강제 종료·PC 종료 또는 콘솔의 Ctrl+C로 종료하면 접수된 주문이 남을 수 있습니다. 통신이 끊기면 중지 파일만으로 취소할 수 없습니다.','Callout')
p('재시작하기','Heading1')
p('토스 주문 내역과 프로그램 상태가 일치하는지 확인합니다. 종료된 상태에서 프로그램 폴더의 STOP 파일만 삭제하고 같은 계좌·설정으로 다시 실행합니다. runtime 안의 상태 파일은 삭제하거나 임의 수정하지 않습니다. 계좌·설정 변경이나 주문 결과 불명확 상태는 먼저 원인을 확인해야 합니다.')
table(['표시 또는 상황','뜻과 조치'],[
 ('UPDATING / COLLECTING_KRX','자료 수집 중. 기다린 후 auto_status.json을 확인'),
 ('READY','분석 완료. 조건·예산에 따라 매수하지 않을 수 있음'),
 ('SETUP_REQUIRED','누락된 인증정보 확인'),('COLLECTION_FAILED / RETRY_WAIT','인증·서비스 점검·접속 장애 확인. 자동 재시도를 기다림'),
 ('OUTSIDE_REGULAR_SESSION','현재 주문 가능 시간 밖. 다음 정규장 확인'),
 ('RESEARCH_OR_CANDIDATE_DATA_UNAVAILABLE','최신 분석 또는 적합한 후보가 없음. 자료·보류 사유 확인'),
 ('BROKER_CONNECTION_WAIT / 403','통신 또는 허용 IP 등 확인. 403의 정확한 원인은 서비스 안내 확인'),
 ('UNKNOWN order outcome','접수 결과 불명확. 반복 실행·재주문 대신 토스 주문 내역과 기록 대조'),
 ('HALTED / 설정 불일치','중단 사유 확인 필요. 상태 파일을 지워 우회하지 않음')])
p('인터넷이 끊기면: 토스 앱에서 주문·보유분 확인 → 연결과 공인 IP 복구 → 프로그램의 주문 상태 대조. 손절·익절이 자동으로 처리됐다고 가정하지 마세요.','Small')

title(8,'기본 설정·파일 위치·공식 안내')
table(['실전 기본 설정','현재 값'],[
 ('원금 / 1회 매수 상한','30,000원 / 9,000원 (비용 여유분 포함)'),('투자 비중 / 보유','평가자산의 30% 한도 / 최대 ETF 1개'),
 ('손절 / 개별 익절 목표','3% / 비용 고려 추정 수익률 10%'),('일 손실 / 최대 낙폭 중단','2% / 10%'),
 ('일·주·월 목표','각 10%. 하나라도 달성하면 청산 시도 후 해당 기간 신규 매수 중단')])
p('매수는 봇의 남은 현금·원화 현금 주문 가능 금액·1회 상한·투자 비중 중 가장 작은 금액을 기준으로 합니다. 신용·대출 기능은 없습니다. 수익·손실은 다음 예산에 반영되지만 9천원 상한을 자동 증액하지 않습니다.')
p('분석은 코스닥 관련 ETF 순자산 상위 최대 20개를 먼저 선정한 후 국내 주식 실물형 1배 상품만 허용합니다. 편입 기업 재무와 뉴스 제목·요약의 규칙 분석을 사용합니다. 기사 전문을 이해하는 AI 분석은 아닙니다. 최신 자료가 없으면 신규 매수를 보류합니다.')
p('찾아볼 파일','Heading1')
p('research/auto_status.json: 수집 상태\nresearch/latest_summary.csv: 순위·보류 사유\nresearch/auto_latest.json: 분석과 출처\nruntime/etf_live_state.json: 실전 주문·보유 기록 (삭제 금지)\nruntime/credentials.dpapi: Windows 암호화 인증정보\nETF_GUIDE.md / LIVE_GUIDE.md: 상세 동작과 주문 복구 안내')
p('공식 안내 및 확인 경로','Heading1')
for s in [
 '[1] 토스 API·허용 IP: https://developers.tossinvest.com/docs/connection',
 '[2] KRX: https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd',
 '[3] OpenDART: https://opendart.fss.or.kr/',
 '[4] DART 점검 안내: https://opendart.fss.or.kr/notice.jsp',
 '[5] API HUB 등록: https://guide.ncloud-docs.com/docs/apihub-application',
 '[6] KRX 수집 라이브러리: https://github.com/sharebook-kr/pykrx',
 '[7] Python 설치: https://www.python.org/downloads/windows/']: p(s,'Small')

title(9,'집 인터넷·테더링 전환과 허용 IP')
p('접속 IP가 바뀌어도 API 키를 새로 발급받을 필요는 없습니다. 기존 Client ID·Client Secret을 유지하고 토스의 허용 IP 목록을 추가·수정하면 됩니다.','Callout')
p('키와 IP는 역할이 다릅니다','Heading1')
p('API 키는 프로그램의 인증정보이고, 허용 IP는 접속을 허용할 인터넷 주소입니다. 인터넷 연결만 변경했다면 프로그램에 저장된 키를 바꾸지 않습니다. 키를 실제로 재발급한 경우에는 GUI의 인증·계좌 설정에서 새 값으로 암호화 저장하세요.')
table(['접속 상황','해야 할 일'],[
 ('집 공유기 사용','집 인터넷에 연결된 PC에서 공인 IP 확인 후 등록'),
 ('휴대폰 테더링 사용','테더링에 연결된 PC에서 공인 IP 확인 후 등록'),
 ('현재 IP가 이미 등록됨','기존 키 그대로 사용하고 읽기 전용 연결 점검'),
 ('현재 IP가 목록에 없음','토스 허용 IP 관리에서 새 주소 추가·수정'),
 ('집과 테더링을 번갈아 사용','등록 화면에서 허용하는 개수 범위 내에 두 공인 IP를 등록. 주소 변경 시 갱신')])
p('네트워크를 바꿀 때의 순서','Heading1')
for s in [
 '1. GUI에서 중지 요청을 누르고 봇 종료를 확인합니다. 보유 종목은 자동 매도되지 않습니다.',
 '2. 토스 앱에서 미체결 주문과 보유분을 확인합니다. 중지 도중 통신이 끊겼다면 취소가 완료됐다고 가정하지 않습니다.',
 '3. PC를 집 인터넷 또는 휴대폰 테더링으로 연결합니다.',
 '4. 그 PC의 브라우저에서 공인 IP를 확인하고 토스증권 웹 → 설정 → Open API → 허용 IP 관리에서 등록 여부를 확인합니다.',
 '5. 필요한 IP를 추가·수정한 뒤 GUI에서 읽기 전용 점검을 시작합니다. STOP 해제 안내가 나오면 기존 주문 확인 후 진행합니다.',
 '6. 계좌·시세 조회가 정상인지 확인합니다. 점검을 중지한 뒤 실전 시작 버튼으로 재개합니다.']:p(s)
p('테더링 재연결과 집의 유동 IP 환경에서는 주소가 달라질 수 있습니다. USB 테더링도 고정 IP를 보장하지 않습니다. 192.168… 같은 내부 주소가 아니라 인터넷에서 보이는 공인 IP를 등록합니다. 이 프로그램은 허용 IP를 자동 등록하지 않습니다.','Small')
p('허용되지 않은 IP에서는 인증 요청이 403으로 거부될 수 있습니다. IP 오류만으로 키를 재발급하지 말고 허용 목록부터 확인하세요. 공식 안내: https://developers.tossinvest.com/docs/auth','Small')

ns='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
styles=f'''<w:styles xmlns:w="{ns}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="맑은 고딕"/><w:sz w:val="21"/><w:color w:val="172B4D"/><w:lang w:val="ko-KR" w:eastAsia="ko-KR"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="110" w:line="290" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults>'''
for name,size,color in [('Normal',21,'172B4D'),('Title',36,'172B4D'),('Heading1',25,'176B63'),('Subtitle',20,'52647B'),('Small',18,'52647B'),('Callout',21,'176B63')]:
    extra='<w:keepNext/>' if name in ('Title','Heading1','Subtitle') else ''
    if name=='Callout': extra+='<w:shd w:fill="E8F3EF"/>'
    styles+=f'<w:style w:type="paragraph" w:styleId="{name}"><w:name w:val="{name}"/><w:pPr>{extra}</w:pPr><w:rPr><w:sz w:val="{size}"/><w:color w:val="{color}"/>'+('<w:b/>' if name in ('Title','Heading1') else '')+'</w:rPr></w:style>'
styles+='</w:styles>'
doc=f'<w:document xmlns:w="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>'+''.join(parts)+'''<w:sectPr><w:footerReference w:type="default" r:id="rId2"/><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1000" w:right="1300" w:bottom="1000" w:left="1300" w:header="450" w:footer="450"/></w:sectPr></w:body></w:document>'''
footer=f'<w:ftr xmlns:w="{ns}"><w:p><w:pPr><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:sz w:val="18"/><w:color w:val="52647B"/></w:rPr><w:t>KoreanStockBot · 사용 매뉴얼   |   </w:t></w:r><w:fldSimple w:instr="PAGE"/></w:p></w:ftr>'
rels='http://schemas.openxmlformats.org/package/2006/relationships'
files={
 '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>',
 '_rels/.rels': f'<Relationships xmlns="{rels}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
 'word/_rels/document.xml.rels': f'<Relationships xmlns="{rels}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>',
 'word/document.xml':doc,'word/styles.xml':styles,'word/footer1.xml':footer}
target=ROOT/'KoreanStockBot_사용매뉴얼.docx'
with ZipFile(target,'w',ZIP_DEFLATED) as z:
    for name,xml in files.items():
        ET.fromstring(xml)
        z.writestr(name,'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+xml)
with ZipFile(target) as z:
    assert z.testzip() is None
    tree=ET.fromstring(z.read('word/document.xml'))
    assert len(tree.findall('.//{'+ns+'}tbl'))==7
print(target)
print('Validated DOCX package, XML parts and 7 tables.')
