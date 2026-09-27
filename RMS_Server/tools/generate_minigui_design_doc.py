from pathlib import Path
from datetime import datetime
from zipfile import ZipFile

from PIL import Image, ImageDraw

import generate_design_doc as g


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "TBC1000B_MiniGUI_V1.0.1.py"
OUT = ROOT / "TBC1000B_MiniGUI_V1.0.1_개발상세설계서.docx"
ASSET = ROOT / "tools" / "minigui_design_doc_assets"
ASSET.mkdir(parents=True, exist_ok=True)


def diagram(title, size=(1600, 1000)):
    im = Image.new("RGB", size, "#F7F9FC")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((28, 24, size[0]-28, size[1]-24), radius=30, fill="white", outline="#D0D9E7", width=3)
    d.text((70, 55), title, font=g.font(42, True), fill="#173B76")
    return im, d


def save_diagrams():
    paths=[]
    p=ASSET/"mini_architecture.png"; im,d=diagram("MiniGUI 논리 아키텍처",(1700,1050))
    g.rounded(d,(80,190,420,360),"운영자\nCustomer Mini UI","#EAF2FF",bold=True)
    g.rounded(d,(640,150,1060,400),"CustomerMiniUI\n간소화 View\n\nBatteryMonitorUI 상속","#DCEAFF",bold=True)
    g.rounded(d,(1280,180,1600,350),"프로파일 INI\n사이트·시스템\nIP·SNMP Port","#FFF2D9")
    g.rounded(d,(80,650,420,825),"TBC1000B / GW\nSNMPv2c UDP 161","#FFE6E6",bold=True)
    g.rounded(d,(640,610,1060,870),"SNMPThread\nminimal_polling\n\nSOC + Rack + EPO 목록","#EFE8FF",bold=True)
    g.rounded(d,(1280,620,1600,820),"EpoCutoffThread\nSOC SET 처리\nQSettings","#E6F7EE")
    g.arrow(d,(420,275),(640,275)); g.arrow(d,(1060,275),(1280,265)); g.arrow(d,(850,400),(850,610)); g.arrow(d,(640,745),(420,745)); g.arrow(d,(1060,745),(1280,720))
    d.text((80,930),"화면에는 핵심 운전 기능만 노출하고, 기존 공통 로직은 상속하여 재사용한다.",font=g.font(27),fill="#53657A")
    im.save(p); paths.append(p)

    p=ASSET/"startup_connect.png"; im,d=diagram("기동 및 접속 상태 전이",(1600,1250))
    nodes=[((480,140,1120,265),"QApplication · profiles 준비","#EAF2FF"),((480,330,1120,455),"ProfileDialog 선택 / 신규 생성","#FFF2D9"),((480,520,1120,645),"Standalone 모드로 CustomerMiniUI 생성","#DCEAFF"),((480,710,1120,835),"IP·Port 검증 → 접속 버튼","#EAF2FF"),((480,900,1120,1025),"sysUpTime 접속 시험","#EFE8FF"),((480,1090,1120,1195),"minimal_polling 시작","#E6F7EE")]
    for i,(xy,t,c) in enumerate(nodes):
        g.rounded(d,xy,t,c,bold=i in (2,5))
        if i:g.arrow(d,(800,nodes[i-1][0][3]),(800,xy[1]))
    g.rounded(d,(1190,855,1510,1000),"실패\nREADY 복귀\n안내 팝업","#FFE6E6",size=23); g.arrow(d,(1120,960),(1190,930))
    im.save(p); paths.append(p)

    p=ASSET/"minimal_polling.png"; im,d=diagram("Minimal Polling 데이터 흐름",(1750,1120))
    g.rounded(d,(80,150,420,300),"Polling cycle\n약 2초 idle","#EAF2FF",bold=True)
    g.rounded(d,(620,120,1090,330),"SNMP GET (5 OIDs)\nSOC enable / value\nRack Ah / V / A","#EFE8FF",bold=True)
    g.rounded(d,(1280,145,1640,305),"rack_info_signal\nsoc_charge_limit_signal","#E6F7EE")
    g.rounded(d,(1280,455,1640,625),"Customer UI 카드\n값·단위·상태 갱신","#DCEAFF",bold=True)
    g.arrow(d,(420,225),(620,225)); g.arrow(d,(1090,225),(1280,225)); g.arrow(d,(1460,305),(1460,455))
    g.rounded(d,(620,690,1090,890),"EPO 모듈 Query\n번호 table + 상태 table\nrow_index별 결합","#FFF2D9",bold=True)
    g.rounded(d,(1280,715,1640,865),"epo_modules_signal\n차단/복구 대상 목록","#E6F7EE")
    g.arrow(d,(855,330),(855,690)); g.arrow(d,(1090,790),(1280,790))
    g.rounded(d,(80,730,420,860),"오류/응답 부족","#FFE6E6"); g.arrow(d,(620,790),(420,790))
    d.text((80,990),"전체 MIB BULK 대신 화면에 필요한 값만 조회하여 초기 표시 시간과 장비 부하를 줄인다.",font=g.font(27),fill="#53657A")
    im.save(p); paths.append(p)

    p=ASSET/"epo_sequence.png"; im,d=diagram("전체 EPO 차단·복구 시퀀스",(1650,1300))
    nodes=[((450,140,1200,260),"버튼: 전체차단 또는 전체복구","#EAF2FF"),((450,325,1200,445),"대상 목록 결정\n차단=alive / 복구=cutoff 상태","#FFF2D9"),((450,510,1200,630),"운영자 확인 및 진행창 생성","#FFE9DE"),((450,695,1200,815),"모듈별 EpoCutoffThread 순차 실행","#EFE8FF"),((450,880,1200,1000),"준비 OID SET → 모듈 OID SET·검증","#EFE8FF"),((450,1065,1200,1185),"결과 집계·성공 시각 저장·UI 갱신","#E6F7EE")]
    for i,(xy,t,c) in enumerate(nodes):
        g.rounded(d,xy,t,c,bold=i in (0,3,4))
        if i:g.arrow(d,(825,nodes[i-1][0][3]),(825,xy[1]))
    g.rounded(d,(1270,720,1570,900),"실패 누적\n후속 모듈 계속","#FFE6E6",size=24); g.arrow(d,(1200,755),(1270,790)); g.arrow(d,(1420,900),(1200,1125))
    im.save(p); paths.append(p)
    return paths


def h1(t): return g.para(t,style="Heading1")
def h2(t): return g.para(t,style="Heading2")
def bullets(items): return ''.join(g.bullet(x) for x in items)


def build_document(diagrams):
    P=[]; A=P.append
    A(g.para("TBC1000B",bold=True,size=34,color="4D6B9B",align="center",before=1050,after=80))
    A(g.para("MiniGUI",bold=True,size=66,color="173B76",align="center",after=60))
    A(g.para("DEVELOPMENT DESIGN SPECIFICATION",bold=True,size=19,color="20A07A",align="center",after=420))
    A(g.para("개발 상세 설계서",bold=True,size=40,color="263B59",align="center",after=520))
    A(g.table(["DOCUMENT","DETAIL"],[["기준 소스","TBC1000B_MiniGUI_V1.0.1.py"],["소스 규모","9,093 lines / Python / PySide6"],["코드 내부 버전","v1.0.0 (파일명 V1.0.1과 불일치)"],["문서 상태","코드 역설계 기준 초안"],["작성일",datetime.now().strftime("%Y-%m-%d")]], [2500,6100]))
    A(g.para("CORE MONITORING  ·  MINIMAL POLLING  ·  SAFE EPO",bold=True,size=17,color="20A07A",align="center",before=500))
    A(g.pagebreak())

    A(h1("문서 관리")); A(h2("개정 이력")); A(g.table(["버전","일자","내용","작성"],[["0.1",datetime.now().strftime("%Y-%m-%d"),"MiniGUI V1.0.1 코드 기준 최초 작성","Codex"],["1.0","승인 시","현장 MIB 및 검토 의견 반영","담당자"]],[1200,1700,4500,1200]))
    A(h2("검토·승인")); A(g.table(["구분","소속/성명","일자","서명"],[["작성","","",""],["검토","","",""],["승인","","",""]],[1300,3100,1900,2300]))
    A(h2("문서 범위")); A(g.para("본 문서는 MiniGUI의 화면, Standalone 기동, 최소 SNMP Polling, SOC 충전 제한, Rack 정보 표시, 전체 모듈 EPO 제어를 중심으로 구현 설계를 설명한다. 상속된 전체 감시 기능은 MiniGUI에서 실제 사용하는 경로와 공통 기반 관점으로 기술한다."))
    A(g.pagebreak())
    A(h1("목차"))
    for x in ["1. 제품 개요","2. MiniGUI 특화 설계","3. 시스템 아키텍처","4. 기동 및 접속 설계","5. 클래스·스레드 설계","6. 화면 상세 설계","7. Minimal Polling 설계","8. 데이터·설정 설계","9. SOC 충전 제한","10. 전체 EPO 차단·복구","11. 예외·성능·보안","12. 시험 및 추적성","부록 A. OID / 부록 B. 코드 검토 결과"]: A(g.para(x,size=20,after=70))
    A(g.pagebreak())

    A(h1("1. 제품 개요")); A(h2("1.1 목적")); A(g.para("현장 운영자가 복잡한 배터리 상세 화면을 거치지 않고 설치 위치와 시스템 접속 정보를 관리하며, Rack 핵심값 확인, SOC 충전 상한 변경, 전체 모듈 긴급 차단·복구를 수행할 수 있는 간결한 데스크톱 UI를 제공한다."))
    A(h2("1.2 핵심 기능")); A(bullets(["설치 장소·축전지명 프로파일 저장","시스템 IP·SNMP Port 검증 및 접속/종료","접속 상태 READY / CONNECTING / ONLINE 표시","Rack 전체용량(Ah), 전압(V), 전류(A) 표시","SOC 충전 제한 사용 여부와 설정값 조회·변경","EPO 전체 차단·복구 및 대상 모듈 수 표시","마지막 업데이트 및 최근 성공 작업 시각 표시","상속된 공통 SNMP/EPO 로직 재사용"] ))
    A(h2("1.3 설계 범위 비교")); A(g.table(["항목","전체 감시 UI","MiniGUI"],[["화면 목적","모듈·셀·알람 상세 운영","핵심 운전·제어"],["Polling","5개 MIB subtree BULK + SOC GET","화면용 5 OID GET + EPO 목록 query"],["Trap listener","기본 활성 경로","ENABLE_SNMP_TRAP_LISTENER=False"],["모드","Master/Slave 가능","Standalone 고정"],["주요 제어","개별/전체 EPO, 기록, 알람 등","SOC 제한, 전체 EPO"],["Main Window","BatteryMonitorUI","CustomerMiniUI(BatteryMonitorUI 상속)"]],[1900,3400,3400]))

    A(h1("2. MiniGUI 특화 설계")); A(h2("2.1 상속 전략")); A(g.para("CustomerMiniUI는 BatteryMonitorUI.__init__으로 공통 설정, 상태 캐시, SNMP 및 EPO 제어 컴포넌트를 초기화한 뒤 고객용 중앙 위젯으로 교체한다. 공통 위젯은 숨겨진 상태 모델/제어 어댑터처럼 남아 있고 Customer UI의 입력과 버튼이 기존 site_edit, system_edit, ip_edit, port_edit 및 공통 제어 메서드로 연결된다."))
    A(h2("2.2 설계 의도")); A(bullets(["공통 로직을 복제하지 않아 EPO/SOC 제어의 동작 일관성을 확보한다.","고객 화면은 업무 빈도가 높은 정보만 카드 형태로 노출한다.","500ms refresh timer가 공통 상태를 읽어 고객용 표시를 동기화한다.","전체 MIB를 매번 읽지 않고 minimal_polling을 사용해 응답성과 장비 부하를 개선한다."]))
    A(h2("2.3 코드상 버전 주의")); A(g.table(["구분","값","판정"],[["파일명","TBC1000B_MiniGUI_V1.0.1.py","배포 식별은 1.0.1"],["VERSION_MAJOR/MINOR/PATCH","1 / 0 / 0","APP_VERSION은 v1.0.0"],["설계 조치","릴리스 전에 상수 또는 파일명을 일치","필수 검토"]],[2300,3800,2500]))

    A(h1("3. 시스템 아키텍처")); A(g.image_para("rIdImg1",6100000,3770000,"mini_architecture")); A(g.para("그림 3-1. MiniGUI 논리 아키텍처",size=17,color="667085",align="center"))
    A(h2("3.1 외부 인터페이스")); A(g.table(["대상","방식","목적","방향"],[["TBC1000B / iIOT GW","SNMPv2c UDP 161","조회 및 제어","양방향"],["파일 시스템","profiles/*.ini","사이트·시스템·접속정보","읽기/쓰기"],["QSettings","로컬 설정","EPO 성공시각 등 상태 유지","읽기/쓰기"],["운영자","Qt Widgets","조회·접속·설정·EPO","양방향"]],[2500,2100,2800,1300]))
    A(h2("3.2 실행 환경")); A(g.table(["구분","내용"],[["언어/GUI","Python 3.x / PySide6 Qt Widgets"],["통신","pysnmp SNMPv2c"],["공통 의존성","psutil, socket, openpyxl 등 전체 기반 모듈 포함"],["리소스","skt_logo.png, pantech.png, 아이콘 및 프로파일"],["기본 모드","Standalone"],["기본 Trap 정책","ENABLE_SNMP_TRAP_LISTENER=False"]],[2200,6400]))

    A(h1("4. 기동 및 접속 설계")); A(g.image_para("rIdImg2",5350000,4180000,"startup_connect")); A(g.para("그림 4-1. 기동·접속 상태 흐름",size=17,color="667085",align="center"))
    A(h2("4.1 시작 순서")); A(g.table(["순서","처리","실패/취소"],[["1","QApplication 생성, profiles 디렉터리 생성","시작 실패 또는 종료"],["2","ProfileDialog에서 기존 INI 선택 또는 신규 생성","데이터 없으면 종료"],["3","mode='Standalone', forced_slave=False 고정","다중 인스턴스 역할 없음"],["4","CustomerMiniUI 생성 및 show","GUI 이벤트 루프 진입"]],[900,4900,2800]))
    A(h2("4.2 접속 입력 검증")); A(bullets(["IP가 비어 있으면 경고 후 요청하지 않는다.","SNMP Port는 정수이며 1~65535 범위여야 한다.","검증된 값을 숨겨진 공통 ip_edit/port_edit에 복사한다.","on_connect_clicked를 호출하여 기존 Ping/SNMP 접속 절차를 사용한다.","접속 대기 중에는 입력과 접속 버튼을 비활성화한다."]))
    A(h2("4.3 상태 전이")); A(g.table(["상태","조건","표현","조작"],[["READY","미접속","회색 점·READY","IP/Port 수정, 접속 시작"],["CONNECTING","connection_start_pending","주황 점·CONNECTING","입력/버튼 잠금"],["ONLINE","is_connected=True","초록 점·ONLINE","접속 종료, SOC/EPO 활성"],["ERROR","Ping/SNMP 실패","안내 후 READY","입력 수정·재시도"]],[1700,2500,2500,1900]))

    A(h1("5. 클래스·스레드 설계")); A(h2("5.1 주요 클래스")); A(g.table(["클래스","책임","MiniGUI 사용"],[["CustomerMiniUI","고객용 화면과 공통 상태 동기화","핵심"],["BatteryMonitorUI","SNMP/EPO/설정 상태 및 공통 제어","상속 기반"],["SNMPThread","접속 시험, minimal/full polling, Rack/EPO query","핵심"],["PingThread","ICMP 생존 확인","접속 단계"],["EpoCutoffThread","준비 OID 및 모듈 OID SET·검증","핵심"],["ProfileDialog","INI 프로파일 선택/생성/삭제","기동"],["SNMPTrapThread","외부 Trap 수신","기본 비활성"],["OperationDataRecordThread","Excel 기록","Mini 화면 미노출"],["ModuleDetailDialog 등","전체 감시 상세 UI","Mini 화면 미노출"]],[2500,4300,1800]))
    A(h2("5.2 Signal 인터페이스")); A(g.table(["Signal","Payload","MiniGUI 처리"],[["result_signal","bool, object","접속 시험/공통 full 결과"],["soc_charge_limit_signal","bool, object","enabled/value 캐시 및 표시"],["rack_info_signal","bool, object","capacity/voltage/current 표시"],["epo_modules_signal","bool, object","alive/restore 모듈 집합"],["initial_load_complete_signal","없음","초기 로딩 완료"],["tx_signal / rx_signal","없음","통신 상태 표시"],["EpoCutoffThread.result_signal","bool,str,int","진행률·결과·다음 모듈"]],[3000,2300,3300]))
    A(h2("5.3 동시성")); A(bullets(["SNMP I/O와 EPO SET은 QThread에서 실행한다.","Qt Signal/Slot으로 UI 스레드에 결과를 전달한다.","Customer refresh는 500ms QTimer로 상태 캐시만 읽는다.","Polling idle은 20×100ms로 나누어 종료 요청에 빠르게 반응한다.","종료 시 running 플래그와 SNMP dispatcher/스레드 wait로 정리한다."]))

    A(h1("6. 화면 상세 설계")); A(h2("6.1 레이아웃")); A(g.table(["영역","컨트롤","동작/표현"],[["브랜드 Header","제목, 모드 badge","READY/CONNECTING/ONLINE"],["프로파일","설치 장소, 축전지명, 저장","필수값 검증 후 QSettings 동기화"],["시스템 접속","IP, SNMP Port, 접속 버튼","접속 상태에 따라 잠금/문구 변경"],["접속 상태","상태 dot, 상태 텍스트, 마지막 갱신","회색/주황/초록"],["Rack 기본정보","전체용량, 전압, 전류 카드","Ah/V/A 단위"],["SOC 충전제한","현재값, 설정 변경","사용=값%, 미사용/미수집"],["EPO","설명, 전체차단, 전체복구, 성공시각","대상 모듈 수와 활성 상태"],["Footer","운영 안내, SKT/Pantech 로고","브랜드/주의 문구"]],[1700,2900,4000]))
    A(h2("6.2 디자인 시스템")); A(g.table(["의미","색상 계열","사용"],[["Primary","#173B76 / Blue","제목·값 강조"],["Success","#12B76A / #067647","ONLINE, SOC 사용, 복구"],["Warning","#F79009","CONNECTING"],["Danger","#D92D20","전체 차단"],["Neutral","#98A2B3 / #EEF2F7","READY, 미수집, 카드 배경"]],[1800,2600,4200]))
    A(h2("6.3 주기 동기화")); A(g.para("refresh_customer_ui는 500ms마다 접속 상태, 마지막 업데이트, Rack 표시값, SOC 설정값, 차단/복구 대상 수, 버튼 활성 상태 및 최근 EPO 성공시각을 공통 상태에서 읽는다. 미접속 시 Rack 값과 SOC 표시를 '-'로 초기화한다."))

    A(h1("7. Minimal Polling 설계")); A(g.image_para("rIdImg3",6250000,3990000,"minimal_polling")); A(g.para("그림 7-1. Minimal Polling 흐름",size=17,color="667085",align="center"))
    A(h2("7.1 파라미터")); A(g.table(["항목","값","의도"],[["SNMP_TIMEOUT_SEC","2.5초","순간 응답 지연 허용"],["SNMP_RETRIES","1회","일시 누락 보완"],["POLL_IDLE_LOOP_COUNT","20","주기 대기 분할"],["POLL_IDLE_SLEEP_MS","100ms","약 2초 주기 및 빠른 종료"],["minimal_polling","True","전체 MIB BULK 생략"]],[2500,1800,4300]))
    A(h2("7.2 단일 GET 요청")); A(g.table(["순서","OID","변환/결과"],[["1","SOC_CHARGE_ENABLE_OID","int → enabled"],["2","SOC_CHARGE_VALUE_OID","int → value %"],["3","RACK_CAPACITY_OID","decode_rack_value → Ah"],["4","RACK_VOLTAGE_OID","decode_rack_value → V"],["5","RACK_CURRENT_OID","decode_rack_value → A"]],[900,4900,2800]))
    A(h2("7.3 오류 처리")); A(bullets(["errorIndication 또는 errorStatus가 있으면 SOC와 Rack signal 모두 실패로 emit한다.","varBinds가 5개 미만이면 '응답값 부족'으로 처리한다.","예외 문자열은 두 실패 signal에 전달한다.","성공 시 RX signal을 한 번 emit하고 SOC/Rack payload를 분리한다.","한 주기 실패가 기존 정상 표시를 어떻게 유지/초기화할지는 각 수신 handler와 refresh 정책을 따른다."]))
    A(h2("7.4 EPO 모듈 조회")); A(g.para("query_epo_modules는 모듈 번호 테이블과 모듈 상태 테이블을 조회하여 row_index별로 결합한다. 결과는 epo_modules_signal을 통해 alive 모듈과 복구 대상 모듈을 구성하고 두 EPO 버튼의 대상 수 및 활성 상태에 반영한다."))

    A(h1("8. 데이터·설정 설계")); A(h2("8.1 영속 설정")); A(g.table(["키/저장소","내용","작성 경로"],[["profiles/*.ini / QSettings","site, system, IP, SNMP Port, community","ProfileDialog / 공통 UI"],["site / system","MiniGUI 설치 장소·축전지명","customer_save_profile_info"],["EPO 성공시각","차단/복구 최근 성공 시각","save_full_epo_success_time"],["리소스 경로","PyInstaller _MEIPASS 또는 실행 경로","resource_path"]],[2800,3400,2400]))
    A(h2("8.2 런타임 상태")); A(g.table(["변수/개념","형태","사용"],[["is_connected","bool","상태 badge와 버튼 활성"],["connection_start_pending","bool","CONNECTING 및 입력 잠금"],["soc_charge_limit_enabled/value","int","미사용 또는 설정 % 표시"],["rack_info","capacity/voltage/current","Rack 카드"],["module_map/module_data","dict","EPO 대상 row_index/상태 기반"],["full_* queue/failures","list/queue","전체 작업 순차 실행"],["customer_refresh_timer","QTimer 500ms","공통→Mini 화면 동기화"]],[2700,2700,3100]))
    A(h2("8.3 프로파일 저장")); A(g.para("설치 장소와 축전지명은 trim 후 빈 문자열을 거부한다. 고객용 입력을 숨겨진 공통 site_edit/system_edit에도 복사하고 QSettings의 site/system key를 갱신한 뒤 sync한다. 실패 시 예외 내용을 오류 팝업으로 표시한다."))

    A(h1("9. SOC 충전 제한")); A(h2("9.1 조회")); A(g.para("minimal polling의 첫 두 OID 결과를 정수화하여 enabled와 value로 전달한다. enabled==2이고 값이 존재하면 녹색 카드에 '{value}%'를 표시하고, 그 외에는 '미사용'으로 표시한다."))
    A(h2("9.2 설정")); A(g.table(["단계","설계"],[["1","접속 및 공통 SOC 버튼 활성 여부 확인"],["2","설정 대화상자에서 사용 여부와 제한값 입력"],["3","Enable OID와 Value OID를 SNMP SET"],["4","errorIndication/errorStatus 및 결과 처리"],["5","다음 polling에서 실제 장비값 재조회 후 화면 동기화"]],[1000,7600]))
    A(h2("9.3 OID")); A(g.table(["명칭","OID"],[["SOC Enable","1.3.6.1.4.1.2011.6.164.1.17.2.1.29.96"],["SOC Value","1.3.6.1.4.1.2011.6.164.1.17.2.1.30.96"]],[2200,6400]))

    A(h1("10. 전체 EPO 차단·복구")); A(g.image_para("rIdImg4",5750000,4520000,"epo_sequence")); A(g.para("그림 10-1. 전체 EPO 작업 시퀀스",size=17,color="667085",align="center"))
    A(h2("10.1 대상 선정")); A(g.table(["작업","대상","명령값"],[["전체 차단","get_alive_module_numbers()","2"],["전체 복구","get_restore_module_numbers()","1"]],[1900,4500,2200]))
    A(h2("10.2 SET 순서")); A(g.table(["순서","OID","검증"],[["1. 준비","1.3.6.1.4.1.2011.6.164.1.2.2.1.1.11.1 = 1","응답 정수 1"],["2. 모듈","1.3.6.1.4.1.2011.6.164.1.18.3.1.2.{row_index}","차단 2 / 복구 1"]],[1500,4900,2200]))
    A(h2("10.3 안전 제어")); A(bullets(["전체 작업 전 운영자 확인 팝업을 표시한다.","대상 모듈을 동시에 실행하지 않고 하나씩 순차 처리한다.","각 SET은 timeout 2초, retry 2회이며 응답값 일치를 검증한다.","실패 모듈은 누적하고 후속 모듈은 계속 처리한다.","진행률과 성공/실패 수를 표시하고 중복 조작을 막는다.","전체 성공 시 차단/복구별 최근 성공시각을 저장해 버튼 아래에 표시한다."]))

    A(h1("11. 예외·성능·보안")); A(h2("11.1 예외/복구")); A(g.table(["상황","처리"],[["IP 누락/Port 오류","접속 전 입력 경고"],["sysUpTime 실패","접속 실패 안내 및 READY 복귀"],["Minimal GET timeout","SOC/Rack 실패 signal"],["응답값 부족/형 변환 오류","실패 처리 및 예외 문자열 전달"],["EPO SET 불일치","해당 모듈 실패 기록, 다음 모듈 진행"],["프로파일 저장 실패","critical 팝업"],["종료 중 polling","running=False, 분할 idle로 빠른 종료"]],[2800,5800]))
    A(h2("11.2 성능")); A(bullets(["5개 화면 OID를 한 번의 GET으로 묶는다.","전체 MIB BULK를 생략하여 패킷 수와 파싱 비용을 줄인다.","500ms UI refresh는 네트워크를 호출하지 않고 캐시만 읽는다.","EPO 대상 목록은 별도 query 결과를 사용한다.","QThread로 네트워크 작업을 분리하여 UI 응답성을 유지한다."]))
    A(h2("11.3 보안")); A(g.para("SNMPv2c community는 평문이며 메시지 인증/암호화가 없다. 프로파일 ACL, 운영망 분리, UDP/161 접근제어, community 로그 마스킹이 필요하다. 전체 EPO는 안전 영향이 큰 기능이므로 사용자 권한, 이중 확인, 감사 로그를 추가하는 것이 바람직하다. 문서에는 코드의 실제 community 문자열을 기재하지 않았다."))
    A(h2("11.4 신뢰성 제약")); A(bullets(["공통 BatteryMonitorUI 전체를 초기화한 후 화면만 교체하므로 숨겨진 타이머/기능의 영향 검토가 필요하다.","MiniGUI와 공통 UI 사이를 위젯 값 복사로 연결해 결합도가 높다.","상태값 enabled==2 등의 의미가 코드 상수로 분리되지 않았다.","Rack 값 decode 규칙은 제조사 MIB의 단위/부호 정의와 대조해야 한다."]))

    A(h1("12. 시험 및 추적성")); tests=[["MG-01","최초 실행/프로파일 생성","Standalone MiniGUI 표시"],["MG-02","빈 설치장소/축전지명 저장","필수값 경고 및 저장 차단"],["MG-03","잘못된 Port","범위 경고, SNMP 요청 없음"],["MG-04","정상 접속","READY→CONNECTING→ONLINE"],["MG-05","잘못된 IP/community","timeout 후 READY 및 안내"],["MG-06","5 OID 정상 응답","SOC, Ah, V, A 단위 표시"],["MG-07","응답 5개 미만","SOC/Rack 실패 처리"],["MG-08","SOC 사용/미사용","값% 녹색 / 미사용 중립 표시"],["MG-09","SOC 변경","SET 후 polling 재조회 일치"],["MG-10","EPO 대상 조회","차단/복구 버튼 모듈 수 일치"],["MG-11","전체 차단 성공","순차 SET, 진행률, 성공시각"],["MG-12","일부 모듈 실패","후속 계속, 실패 수/상세 표시"],["MG-13","접속 중 입력","IP/Port/버튼 비활성"],["MG-14","통신 중 종료","UI hang 없이 스레드 종료"],["MG-15","버전 표시","파일명과 APP_VERSION 일치 확인"]]
    A(g.table(["ID","시나리오","기대 결과"],tests,[1100,3300,4300]))
    A(h2("12.1 기능 추적")); A(g.table(["요구 기능","구현","시험"],[["프로파일","customer_save_profile_info","MG-01,02"],["접속","customer_toggle_connection / 공통 접속","MG-03~05,13"],["Rack/SOC 조회","run_minimal_polling / refresh_customer_ui","MG-06~08"],["SOC 설정","open_soc_charge_limit_dialog / SET","MG-09"],["전체 EPO","full EPO queue / EpoCutoffThread","MG-10~12"],["종료/버전","closeEvent / version constants","MG-14,15"]],[2200,4300,2100]))

    A(h1("부록 A. MiniGUI OID")); A(g.table(["기능","OID","방식"],[["접속 시험","1.3.6.1.2.1.1.3.0","GET"],["SOC Enable","1.3.6.1.4.1.2011.6.164.1.17.2.1.29.96","GET/SET"],["SOC Value","1.3.6.1.4.1.2011.6.164.1.17.2.1.30.96","GET/SET"],["Rack Capacity","1.3.6.1.4.1.2011.6.164.1.17.1.1.7.96","GET"],["Rack Voltage","1.3.6.1.4.1.2011.6.164.1.17.1.1.5.96","GET"],["Rack Current","1.3.6.1.4.1.2011.6.164.1.17.1.1.6.96","GET"],["EPO 모듈 번호","1.3.6.1.4.1.2011.6.164.1.18.1.1.4","Table query"],["EPO 모듈 상태","1.3.6.1.4.1.2011.6.164.1.18.2.1.3","Table query"],["EPO 준비","1.3.6.1.4.1.2011.6.164.1.2.2.1.1.11.1","SET 1"],["모듈 EPO","1.3.6.1.4.1.2011.6.164.1.18.3.1.2.{row}","SET 2/1"]],[2100,5000,1500]))
    A(g.para("정확한 데이터 형식, 단위 배율, signed 값, Enable 코드 및 EPO 허용값은 제조사 MIB를 최종 기준으로 승인한다.",size=17,color="667085"))
    A(h1("부록 B. 코드 검토 결과")); A(g.table(["우선순위","관찰 사항","권고"],[["높음","파일명 V1.0.1과 APP_VERSION v1.0.0 불일치","릴리스 식별 통일"],["높음","EPO는 안전 중요 기능이나 권한/감사 로그 없음","권한·작업자·대상·결과 로그"],["높음","SNMPv2c community 평문","보안 저장소 또는 SNMPv3"],["중간","CustomerMiniUI가 대형 공통 UI 전체를 상속/초기화","Mini service/controller 분리"],["중간","Magic value enabled==2, command 1/2","Enum/상수 및 MIB schema"],["중간","화면 refresh 500ms와 polling 약 2초가 독립","데이터 timestamp/신선도 표시"],["낮음","공통 코드 중 Mini 미사용 기능이 배포물에 포함","의존성/패키지 크기 정리"]],[1200,3700,3700]))
    A(h2("검토 기준")); A(g.para("본 문서는 TBC1000B_MiniGUI_V1.0.1.py의 정적 코드 분석을 바탕으로 작성했다. 실제 장비 MIB, 현장 네트워크, EPO 안전 절차 및 UI 승인 기준을 입수하면 OID 의미, 단위, 허용 범위와 시험 결과를 갱신해야 한다."))
    sect='''<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader1"/><w:footerReference w:type="default" r:id="rIdFooter1"/><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1050" w:right="950" w:bottom="950" w:left="950" w:header="480" w:footer="480"/><w:cols w:space="708"/><w:docGrid w:linePitch="360"/></w:sectPr>'''
    return ''.join(P)+sect


if __name__ == "__main__":
    assert SOURCE.exists(), SOURCE
    g.OUT=OUT
    g.build_document=build_document
    g.make_docx(save_diagrams())
    with ZipFile(OUT) as z:
        assert z.testzip() is None
    print(OUT)
    print(OUT.stat().st_size)
