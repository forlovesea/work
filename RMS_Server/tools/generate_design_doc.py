from pathlib import Path
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape
import struct

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = next(ROOT.glob("TBC1000B_*V3.2.3.py"))
OUT = ROOT / "TBC1000B_감시프로그램_V3.2.3_개발상세설계서.docx"
ASSET = ROOT / "tools" / "design_doc_assets"
ASSET.mkdir(parents=True, exist_ok=True)


def font(size=28, bold=False):
    candidates = [
        Path("C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def rounded(draw, xy, text, fill, outline="#35506b", radius=18, size=26, bold=False):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=3)
    f = font(size, bold)
    box = draw.multiline_textbbox((0, 0), text, font=f, spacing=6, align="center")
    tw, th = box[2] - box[0], box[3] - box[1]
    cx = (xy[0] + xy[2]) / 2
    cy = (xy[1] + xy[3]) / 2
    draw.multiline_text((cx - tw / 2, cy - th / 2), text, font=f, fill="#152536", spacing=6, align="center")


def arrow(draw, start, end, color="#46637f", width=5):
    draw.line([start, end], fill=color, width=width)
    import math
    a = math.atan2(end[1] - start[1], end[0] - start[0])
    l = 18
    p1 = (end[0] - l * math.cos(a - 0.55), end[1] - l * math.sin(a - 0.55))
    p2 = (end[0] - l * math.cos(a + 0.55), end[1] - l * math.sin(a + 0.55))
    draw.polygon([end, p1, p2], fill=color)


def save_diagrams():
    paths = []

    p = ASSET / "architecture.png"
    im = Image.new("RGB", (1600, 920), "white"); d = ImageDraw.Draw(im)
    d.text((50, 30), "시스템 논리 아키텍처", font=font(42, True), fill="#15324b")
    rounded(d, (80, 160, 430, 300), "운영자\n(PySide6 GUI)", "#e8f1fb", bold=True)
    rounded(d, (625, 130, 1010, 330), "BatteryMonitorUI\n상태·제어 오케스트레이션", "#d8ebff", bold=True)
    rounded(d, (1180, 110, 1520, 250), "프로파일 / QSettings\nINI · master_profile.txt", "#fff1d6")
    rounded(d, (1180, 315, 1520, 455), "운전 데이터 기록\nExcel(openpyxl)", "#e4f7ea")
    rounded(d, (90, 500, 430, 660), "TBC1000B / iIOT GW\nSNMP GET·BULK·SET\nUDP 161 / Trap 162", "#ffe5e5", bold=True)
    rounded(d, (625, 485, 1010, 665), "Worker Threads\nSNMP · Trap · EPO\nPing · Record", "#efe7ff", bold=True)
    rounded(d, (1180, 530, 1520, 690), "Master / Slave 중계\nUDP 50000 + Local Trap", "#e8f7f7")
    arrow(d, (430, 230), (625, 230)); arrow(d, (1010, 200), (1180, 180)); arrow(d, (1010, 290), (1180, 375))
    arrow(d, (625, 575), (430, 575)); arrow(d, (815, 330), (815, 485)); arrow(d, (1010, 575), (1180, 610))
    d.text((50, 820), "Qt Signal/Slot으로 UI 스레드와 작업 스레드 사이의 결과를 전달한다.", font=font(27), fill="#334b60")
    im.save(p); paths.append(p)

    p = ASSET / "startup_flow.png"
    im = Image.new("RGB", (1350, 1500), "white"); d = ImageDraw.Draw(im)
    d.text((50, 25), "프로그램 시작 및 접속 흐름", font=font(42, True), fill="#15324b")
    boxes = [
        ((390, 110, 960, 215), "QApplication 생성"),
        ((390, 275, 960, 400), "profiles 디렉터리 생성\nQLockFile로 최초 인스턴스 판정"),
        ((390, 460, 960, 585), "ProfileDialog\n기존 프로파일 선택 또는 신규 생성"),
        ((390, 645, 960, 770), "Master / Slave 모드 결정\n강제 Slave 여부 반영"),
        ((390, 830, 960, 955), "BatteryMonitorUI 생성\n설정·화면·스레드 초기화"),
        ((390, 1015, 960, 1140), "접속 요청: PingThread로 통신 확인"),
        ((390, 1200, 960, 1325), "SNMP polling / Trap listener 시작\n주기적으로 UI 갱신"),
    ]
    for i, (xy, txt) in enumerate(boxes):
        rounded(d, xy, txt, "#e8f1fb" if i < 5 else "#e4f7ea", bold=(i in (0,4,6)))
        if i: arrow(d, (675, boxes[i-1][0][3]), (675, xy[1]))
    im.save(p); paths.append(p)

    p = ASSET / "poll_trap_flow.png"
    im = Image.new("RGB", (1700, 1150), "white"); d = ImageDraw.Draw(im)
    d.text((50, 25), "Polling과 Trap 처리 흐름", font=font(42, True), fill="#15324b")
    rounded(d, (80, 130, 470, 270), "Polling Timer", "#e8f1fb", bold=True)
    rounded(d, (650, 130, 1050, 270), "SNMPThread\nGET uptime → BULK walk", "#efe7ff", bold=True)
    rounded(d, (1230, 130, 1620, 270), "handle_snmp_result\nOID 파싱·캐시 갱신", "#e4f7ea", bold=True)
    rounded(d, (1230, 405, 1620, 550), "요약/모듈/상세 화면\n알람 상태 갱신", "#d8ebff")
    arrow(d, (470, 200), (650, 200)); arrow(d, (1050, 200), (1230, 200)); arrow(d, (1425, 270), (1425, 405))
    rounded(d, (80, 680, 470, 825), "SNMPTrapThread\nUDP 162 수신", "#ffe5e5", bold=True)
    rounded(d, (650, 680, 1050, 825), "Trap varBind → dict\nsource IP·수신시각 부가", "#fff1d6")
    rounded(d, (1230, 650, 1620, 855), "handle_trap\n알람/복구 판정\n로그·팝업·점멸·음향", "#e4f7ea", bold=True)
    arrow(d, (470, 750), (650, 750)); arrow(d, (1050, 750), (1230, 750))
    arrow(d, (1425, 650), (1425, 550))
    d.text((105, 930), "Master 모드", font=font(28, True), fill="#334b60")
    arrow(d, (280, 825), (280, 1010)); rounded(d, (450, 925, 1050, 1060), "등록된 Slave의 Local Trap 포트로 JSON/UDP 중계", "#e8f7f7")
    arrow(d, (280, 1010), (450, 995))
    im.save(p); paths.append(p)

    p = ASSET / "epo_flow.png"
    im = Image.new("RGB", (1500, 1450), "white"); d = ImageDraw.Draw(im)
    d.text((50, 25), "모듈 EPO 차단/복구 흐름", font=font(42, True), fill="#15324b")
    nodes = [
        ((430, 110, 1070, 220), "운영자 명령 및 확인 팝업", "#e8f1fb"),
        ((430, 280, 1070, 400), "대상 모듈/row_index/명령값 결정", "#fff1d6"),
        ((430, 460, 1070, 580), "EPO 준비 OID SET = 1 및 응답값 검증", "#efe7ff"),
        ((430, 640, 1070, 760), "모듈 차단 OID.{row_index} SET\n차단=2, 복구=1 및 응답값 검증", "#efe7ff"),
        ((430, 820, 1070, 940), "결과 Signal(bool, message, module_no)", "#e4f7ea"),
        ((430, 1000, 1070, 1120), "버튼/상태/진행률 갱신", "#d8ebff"),
        ((430, 1180, 1070, 1300), "전체 작업이면 다음 모듈 순차 실행", "#e8f7f7"),
    ]
    for i,(xy,txt,c) in enumerate(nodes):
        rounded(d, xy, txt, c, bold=i in (0,2,3,6))
        if i: arrow(d, (750, nodes[i-1][0][3]), (750, xy[1]))
    d.text((1090, 510), "실패", font=font(25, True), fill="#b91c1c"); arrow(d, (1070, 520), (1300, 520))
    rounded(d, (1190, 570, 1430, 730), "실패 사유 저장\n다음 대상 진행", "#ffe5e5", size=23)
    arrow(d, (1310, 730), (1070, 1240))
    im.save(p); paths.append(p)
    return paths


def xrun(text, bold=False, size=20, color="000000", fontname="맑은 고딕"):
    b = "<w:b/>" if bold else ""
    return f'<w:r><w:rPr>{b}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/><w:rFonts w:ascii="{fontname}" w:hAnsi="{fontname}" w:eastAsia="{fontname}"/><w:color w:val="{color}"/></w:rPr><w:t xml:space="preserve">{escape(str(text))}</w:t></w:r>'


def para(text="", style=None, bold=False, size=20, color="000000", align=None, before=0, after=100, keep=False):
    pp=[]
    if style: pp.append(f'<w:pStyle w:val="{style}"/>')
    if align: pp.append(f'<w:jc w:val="{align}"/>')
    pp.append(f'<w:spacing w:before="{before}" w:after="{after}" w:line="300" w:lineRule="auto"/>')
    if keep: pp.append('<w:keepNext/>')
    return f'<w:p><w:pPr>{"".join(pp)}</w:pPr>{xrun(text,bold,size,color)}</w:p>'


def bullet(text, level=0):
    return f'<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="1"/></w:numPr><w:spacing w:after="70"/></w:pPr>{xrun(text,False,19)}</w:p>'


def pagebreak(): return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def table(headers, rows, widths=None):
    data=[headers]+rows
    cols=len(headers); widths=widths or [int(9000/cols)]*cols
    out=['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>']
    out += [f'<w:gridCol w:w="{w}"/>' for w in widths]
    out.append('</w:tblGrid>')
    for ri,row in enumerate(data):
        out.append('<w:tr>')
        for ci in range(cols):
            val=row[ci] if ci<len(row) else ''
            shade='<w:shd w:fill="D9EAF7"/>' if ri==0 else ''
            out.append(f'<w:tc><w:tcPr><w:tcW w:w="{widths[ci]}" w:type="dxa"/>{shade}<w:vAlign w:val="center"/></w:tcPr>{para(val,bold=ri==0,size=17,align="center" if ri==0 else None,after=45)}</w:tc>')
        out.append('</w:tr>')
    out.append('</w:tbl>')
    return ''.join(out)


def image_para(rid, cx, cy, name):
    doc_pr_id = int(''.join(ch for ch in rid if ch.isdigit()))
    return f'''<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{doc_pr_id}" name="{escape(name)}"/><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{doc_pr_id}" name="{escape(name)}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''


def build_document(diagrams):
    parts=[]; P=parts.append
    P(para("TBC1000B 감시프로그램", bold=True, size=44, color="17365D", align="center", before=1100, after=250))
    P(para("개발 상세 설계서", bold=True, size=54, color="1F4E78", align="center", after=500))
    P(para("기준 소스: TBC1000B_감시프로그램_V3.2.3.py", size=22, align="center", after=100))
    P(para("애플리케이션 버전: v3.2.3", size=22, align="center", after=850))
    P(table(["문서 항목","내용"], [["문서 상태","초안(코드 역설계 기준)"],["작성 기준일",datetime.now().strftime("%Y-%m-%d")],["기준 코드","8,729 lines / Python / PySide6"],["보안 등급","프로젝트 내부 사용"]],[2400,6200]))
    P(para("※ 본 문서는 소스 코드 정적 분석 결과를 기준으로 작성되었으며, 장비 MIB 원문·현장 운용 규칙·요구사항 명세가 추가되면 검토/승인이 필요하다.", size=17, color="666666", before=500, align="center"))
    P(pagebreak())

    P(para("문서 관리",style="Heading1"))
    P(para("개정 이력",style="Heading2"))
    P(table(["버전","일자","변경 내용","작성"],[["0.1",datetime.now().strftime("%Y-%m-%d"),"v3.2.3 코드 기준 최초 작성","Codex"],["1.0","승인 시","검토 의견 및 현장 규격 반영","담당자"]],[1200,1700,4600,1200]))
    P(para("검토 및 승인",style="Heading2"))
    P(table(["구분","소속/성명","일자","서명"],[["작성","","",""],["검토","","",""],["승인","","",""]],[1300,3200,1900,2200]))
    P(para("문서 범위",style="Heading2"))
    P(para("본 설계서는 단일 Python 파일에 구현된 TBC1000B-NDA1 / IoT Gateway Battery Monitoring System(Base SNMPv2)의 구조와 동작을 유지보수 가능한 단위로 설명한다. 설치 프로그램, 장비 펌웨어 내부, MIB 원문 설계는 범위 밖이다."))
    P(pagebreak())

    P(para("목차",style="Heading1"))
    toc=["1. 개요","2. 시스템 컨텍스트 및 아키텍처","3. 실행 환경과 배포","4. 프로그램 시작/종료 설계","5. 클래스 및 스레드 상세 설계","6. 데이터 및 설정 설계","7. SNMP 통신 상세 설계","8. Polling 데이터 처리 설계","9. Trap·알람 처리 설계","10. Master/Slave 연동 설계","11. EPO 차단/복구 설계","12. 운전 데이터 기록 설계","13. UI 상세 설계","14. 예외·복구·성능·보안 설계","15. 시험 설계 및 추적성","부록 A. OID 목록 / 부록 B. 유지보수 권고"]
    for x in toc: P(para(x,size=20,after=70))
    P(pagebreak())

    P(para("1. 개요",style="Heading1"))
    P(para("1.1 목적",style="Heading2")); P(para("배터리 모듈과 iIOT Gateway의 상태를 SNMPv2로 감시하고, Trap 기반 장애 통보, 다중 인스턴스 연동, 원격 EPO, 운전 데이터 보존 기능을 제공하는 데스크톱 애플리케이션의 구현 설계를 정의한다."))
    P(para("1.2 주요 기능",style="Heading2"))
    for x in ["프로파일 기반 사이트/시스템 접속 정보 관리","ICMP Ping 후 SNMP GET/BULK polling 수행","최대 10개 모듈의 전압·전류·SOC·SOH·셀 전압·온도·상태 표시","SNMP Trap 수신, 장애/복구 판정, 로그·팝업·음향·점멸 처리","Master가 Slave를 등록하고 Trap JSON을 로컬 UDP 포트로 중계","충전 전류 제한 및 SOC 충전 제한 GET/SET","모듈별 또는 전체 EPO 차단/복구","선택 필드의 주기별 Excel 기록","모듈 상세/전체 상세/알람 목록/Slave 목록 대화상자"]: P(bullet(x))
    P(para("1.3 용어",style="Heading2"))
    P(table(["용어","정의"],[["Polling","일정 주기로 SNMP GET/BULK를 수행해 현재 상태를 취득하는 방식"],["Trap","장비가 UDP로 비동기 전송하는 SNMP 알림"],["Master","외부 Trap을 직접 수신하고 등록된 Slave에 중계하는 최초 인스턴스"],["Slave","로컬 Trap 포트를 할당받아 Master의 중계 데이터를 수신하는 추가 인스턴스"],["row_index","SNMP 장비 테이블의 행 식별자. 화면 모듈 번호와 별도 매핑됨"],["EPO","모듈 출력의 긴급 차단/복구 제어"]],[1700,6900]))

    P(para("2. 시스템 컨텍스트 및 아키텍처",style="Heading1"))
    P(image_para("rIdImg1", 6000000, 3450000, "architecture"))
    P(para("그림 2-1. 시스템 논리 아키텍처",size=17,color="666666",align="center"))
    P(para("2.1 설계 원칙",style="Heading2"))
    for x in ["GUI 이벤트 루프는 네트워크/파일 I/O를 직접 장시간 블로킹하지 않고 QThread 작업자로 분리한다.","작업 결과는 Qt Signal/Slot으로 메인 UI에 전달한다.","Polling 결과는 module_map, module_data, system_summary 캐시에 저장한 후 여러 화면에서 재사용한다.","Trap은 Polling보다 즉시성이 높은 상태 변화 입력으로 처리하되 이후 Polling 상태와 합성한다.","다중 인스턴스는 QLockFile로 최초 인스턴스를 Master로 식별하고 나머지는 Slave로 제한한다."] : P(bullet(x))
    P(para("2.2 외부 인터페이스",style="Heading2"))
    P(table(["대상","방식/포트","방향","목적"],[["TBC1000B/iIOT GW","ICMP","양방향","접속 전 생존 확인"],["SNMP Agent","SNMPv2c UDP/161","요청/응답","상태 조회 및 제어"],["SNMP Trap Sender","UDP/162(기본)","수신","알람/복구 이벤트"],["Master/Slave","JSON over UDP/50000","양방향","Slave 등록/해제"],["Master→Slave","JSON over UDP/동적 localhost 포트","단방향","Trap 중계"],["파일 시스템","INI/TXT/XLSX/WAV/PNG","읽기/쓰기","설정·상태·기록·리소스"]],[2100,2300,1600,2600]))

    P(para("3. 실행 환경과 배포",style="Heading1"))
    P(table(["구분","설계 내용"],[["언어","Python 3.x"],["GUI","PySide6(Qt Widgets, Qt Multimedia)"],["SNMP","pysnmp hlapi 및 entity/rfc3413 Trap receiver"],["Excel","openpyxl"],["시스템","psutil, socket, subprocess, threading/queue"],["패키징","PyInstaller one-file/windowed 방식이 소스 주석에 제시됨"],["주요 리소스","alarm.wav, install_battery.png, battery 아이콘, profiles 디렉터리"]],[2200,6400]))
    P(para("3.1 실행 전제",style="Heading2"))
    for x in ["Windows에서 Trap UDP 162를 점유하는 SNMPTRAP/MgWTrap3 등 타 프로세스와 포트 충돌이 없어야 한다.","SNMP Read/Write/Trap community는 현장 장비 설정과 일치해야 한다.","UDP 161/162 및 Master/Slave 통신 포트가 방화벽 정책에 허용되어야 한다.","운전 기록 디렉터리에 충분한 쓰기 권한과 여유 공간이 있어야 한다."] : P(bullet(x))

    P(para("4. 프로그램 시작/종료 설계",style="Heading1"))
    P(image_para("rIdImg2", 5000000, 5550000, "startup_flow")); P(para("그림 4-1. 시작 및 접속 흐름",size=17,color="666666",align="center"))
    P(para("4.1 시작 순서",style="Heading2"))
    P(table(["순서","처리","실패 시 동작","코드 위치"],[["1","QApplication 생성","프로세스 종료","8630 이후"],["2","profiles 디렉터리 확보","OS 예외로 시작 실패","8635 이후"],["3","app.lock 획득","실패하면 forced_slave=True","8643 이후"],["4","최초 인스턴스이면 master_profile.txt 정리","정리 실패는 디버그 로그 후 계속","8659 이후"],["5","프로파일 선택/신규 생성","취소 또는 데이터 없음이면 종료","8672 이후"],["6","BatteryMonitorUI 생성·show","예외 발생 시 시작 실패","8725 이후"]],[800,3400,2800,1200]))
    P(para("4.2 종료 순서",style="Heading2")); P(para("closeEvent는 타이머와 기록 작업을 정지하고 각 QThread에 stop/quit/wait를 수행하며, 소켓 또는 SNMP dispatcher를 닫아 블로킹 수신을 해제한다. Master/Slave 등록 상태와 임시 파일도 모드에 맞게 정리한다. 종료 대기는 스레드별 제한 시간을 두어 UI 무한 정지를 방지한다."))

    P(para("5. 클래스 및 스레드 상세 설계",style="Heading1"))
    P(para("5.1 클래스 책임",style="Heading2"))
    rows=[
        ["BatteryMonitorUI","QMainWindow","전체 상태, 화면, Polling/Trap/EPO/기록 작업 조정","1969"],
        ["SNMPThread","QThread","uptime GET, 다중 subtree BULK, 결과 emit","1721"],
        ["SNMPTrapThread","QThread","외부 SNMP Trap listener 및 varBind dict 변환","1244"],
        ["LocalTrapReceiver","QThread","Slave의 localhost JSON Trap 수신","8555"],
        ["PingThread","QThread","플랫폼별 ping 1회 수행","461"],
        ["SlaveRegisterThread","QThread","UDP 50000의 Slave 등록 메시지 수신","1409"],
        ["TrapRetransmitSetThread","QThread","장비 Trap 재전송 SNMP SET","1459"],
        ["EpoCutoffThread","QThread","EPO 준비 및 모듈 차단/복구 SET·응답 검증","1506"],
        ["OperationDataRecordThread","QThread","queue의 스냅샷을 날짜별 XLSX로 기록","1614"],
        ["ProfileDialog","QDialog","프로파일 검색/생성/삭제/선택","986"],
        ["ModuleOrderDialog","QDialog","모듈 표시 순서 입력·중복검사·저장","241"],
        ["ModuleDetailDialog","QDialog","개별 모듈 상세 데이터 표시","499"],
        ["AllModuleDetailDialog","QDialog","전체 모듈 상세 데이터 표시","802"],
        ["SlaveListDialog","QDialog","등록 Slave/프로파일 목록 표시","8348"],
        ["AlarmListDialog","QDialog","알람명과 설명 목록 표시","8438"],
    ]
    P(table(["클래스","기반","책임","시작행"],rows,[2300,1400,4300,900]))
    P(para("5.2 Signal 인터페이스",style="Heading2"))
    P(table(["발신 클래스","Signal","Payload","수신 처리"],[["PingThread","ping_result","bool, str","접속 가능 여부 처리"],["SNMPThread","result_signal","bool, object","handle_snmp_result"],["SNMPThread","soc_charge_limit_signal","bool, object","SOC 제한 결과 처리"],["SNMPThread","initial_load_complete_signal","없음","초기 로딩 팝업 종료"],["SNMPTrapThread","trap_signal","dict","handle_trap"],["SNMPTrapThread","listener_status_signal","bool, str","포트 bind 결과 안내"],["SlaveRegisterThread","register_signal","dict","handle_register"],["EpoCutoffThread","result_signal","bool, str, int","모듈별 EPO 결과 처리"],["OperationDataRecordThread","saved_signal/error_signal","path,row_count / message","기록 상태 UI"]],[2100,2700,2100,2200]))
    P(para("5.3 동시성 규칙",style="Heading2"))
    for x in ["QWidget 변경은 메인 UI 스레드의 slot에서만 수행한다.","장시간 SNMP setCmd/getCmd/bulkCmd, UDP recvfrom 및 Excel 저장은 작업 스레드에서 수행한다.","OperationDataRecordThread 입력 queue는 UI의 스냅샷 생성과 파일 쓰기를 분리한다.","Trap queue는 deque(maxlen=2000)으로 제한하며 오래된 항목은 자동 제거한다.","종료 시 running 플래그 설정 후 socket.close/dispatcher.close로 블로킹 호출을 깨운다."] : P(bullet(x))

    P(para("6. 데이터 및 설정 설계",style="Heading1"))
    P(para("6.1 런타임 핵심 데이터",style="Heading2"))
    P(table(["데이터","키/형태","용도"],[["module_map","module_no → {row_index,equip_id,model,barcode,…}","표시 번호와 SNMP 테이블 행 매핑"],["module_data","row_index → {volt,current,soc,soh,status,cells,temps,…}","Polling 최신값 캐시"],["system_summary","dict","시스템 전압/전류/SOC/SOH/상태 요약"],["faults","모듈·셀 기반 항목 목록","현재 장애 테이블"],["trap_log","최대 1,000건","시간/OID/알람/등급/장비 이력"],["slave_targets","Slave 식별자/주소/로컬 포트","Trap 중계 대상"],["module_order","1~10 표시 순서","물리 설치 순서 반영"],["cutoff_buttons","module_no → QPushButton","EPO 상태 및 조작 연결"]],[2100,3900,2900]))
    P(para("6.2 영속 데이터",style="Heading2"))
    P(table(["저장소","주요 내용","수명/정책"],[["profiles/*.ini","사이트, 시스템, IP, SNMP 포트/community, 화면 설정","프로파일별 유지"],["QSettings","모듈 순서, 기록 주기/필드/기간, UI 선택값","사용자/애플리케이션 설정"],["profiles/master_profile.txt","현재 Master가 점유한 프로파일 식별","최초 인스턴스 시작/종료 시 관리"],["app.lock","최초 인스턴스 잠금","프로세스 수명"],["Operation_data_*.xlsx","날짜별 운전 데이터","운영자 보존 정책"],["Trap log","UI 메모리 기반 최대 1,000건","프로세스 수명"]],[2600,3800,2500]))
    P(para("6.3 값 변환",style="Heading2")); P(para("SNMP prettyPrint 문자열은 OID별 의미에 따라 정수/실수로 변환되고 장비 단위 배율을 적용한다. 모듈 상태 코드는 0 Online, 1 Offline, 2 Sleep, 3 Disconnect, 4 Charging, 5 Discharging, 6 Standby, 255 Unknown으로 표시한다. 셀 전압과 온도는 각각 최대 15개를 보존하고 부족한 값은 None으로 채운다."))

    P(para("7. SNMP 통신 상세 설계",style="Heading1"))
    P(para("7.1 통신 파라미터",style="Heading2")); P(table(["항목","값/정책"],[["SNMP 버전","v2c (CommunityData mpModel=1)"],["Agent 기본 포트","UDP 161, 프로파일에서 변경 가능"],["Trap 기본 포트","UDP 162"],["SET timeout/retry","2초 / 2회(EPO, 재전송 작업 기준)"],["Read/Write/Trap community","프로파일/기본값 사용; 코드 주석 기본 예시는 각각 별도 값"],["수신 주소","외부 Trap 0.0.0.0, Slave Local Trap 127.0.0.1"]],[2500,6100]))
    P(para("7.2 Polling 요청",style="Heading2")); P(para("SNMPThread는 먼저 sysUpTime OID를 GET하여 기본 통신을 확인한 뒤 모듈 테이블, 모듈 측정값, 시스템 요약, 알람 관련 subtree를 bulkCmd로 순회한다. 결과는 OID 문자열을 key로 하는 데이터로 수집해 result_signal로 전달한다. once 모드는 접속 시험/초기 작업에 사용되고 일반 모드는 반복 Polling에 사용된다."))
    P(para("7.3 SET 공통 검증",style="Heading2"));
    for x in ["errorIndication이 있으면 통신 실패로 처리한다.","errorStatus가 있으면 SNMP 상태와 errorIndex를 실패 사유에 포함한다.","varBinds가 비었으면 응답값 없음으로 실패 처리한다.","EPO는 반환값을 정수화하여 요청 expected_value와 일치하는지 확인한다.","성공/실패 결과는 Signal로 UI에 전달하며 UI에서 버튼 및 팝업을 갱신한다."] : P(bullet(x))

    P(para("8. Polling 데이터 처리 설계",style="Heading1"))
    P(image_para("rIdImg3", 6100000, 4120000, "poll_trap_flow")); P(para("그림 8-1. Polling 및 Trap 처리",size=17,color="666666",align="center"))
    P(para("8.1 OID 분류 및 캐시 갱신",style="Heading2"))
    P(table(["OID 영역","해석 결과","반영 대상"],[["…1.1.2.99.1.2.*","알람 ordinal/관련 필드","알람 매핑"],["…1.1.2.99.1.3.*","알람 level","알람 severity"],["…1.1.2.99.1.5.*","알람 문자열/상태","알람 UI"],["…1.1.2.99.1.10.*","추가 알람 속성","알람 처리"],["…1.17.1.1.*.96","시스템 요약값","요약 화면"],["…1.18.1.1.{2,4,5,12,13}.*","장비 ID/주소/SW/모델/바코드","module_map"],["…1.18.2.1.3.*","모듈 측정/상태 행","module_data"]],[3000,2900,2700]))
    P(para("8.2 화면 갱신 순서",style="Heading2"))
    for x in ["SNMP 성공 여부 확인 및 연결 상태 갱신","장비 테이블에서 실제 모듈 번호와 row_index 매핑 구성","측정 OID를 row_index별 module_data로 집계","모듈 순서 설정에 따라 좌/우 테이블 1~10행 배치","전압·전류·SOC·SOH·상태 및 알람 셀 스타일 갱신","요약값, 바코드 불일치, EPO 버튼 활성 상태 갱신","열려 있는 개별/전체 상세 대화상자에 최신값 반영"] : P(bullet(x))
    P(para("8.3 실패 처리",style="Heading2")); P(para("Polling 실패 시 연결/요약/모듈 UI를 실패 상태로 전환하고, 기존 스레드를 안전하게 정리한다. 초기 접속 단계에서는 사용자에게 IP, 포트, community, 방화벽, Trap 포트 점유 여부를 확인하도록 안내 메시지를 제공한다."))

    P(para("9. Trap·알람 처리 설계",style="Heading1"))
    P(para("9.1 Trap 수신",style="Heading2")); P(para("SNMPTrapThread는 지정 IP/포트에 UDP transport를 bind하고 pysnmp NotificationReceiver callback을 등록한다. callback은 송신지 IP를 추출하고 varBind를 OID 문자열→prettyPrint 값 dict로 변환한다. 수신 LED, 마지막 수신 시각, 초당 Trap rate를 갱신하고 trap_queue와 UI signal에 전달한다."))
    P(para("9.2 Trap 분류",style="Heading2"))
    P(table(["Trap OID","의미","처리"],[["…2.1.3.0.99","ACB alarm","장애 등록"],["…2.1.3.0.100","ACB alarm resume","장애 복구"],["…2.1.15.0.1","Cabinet alarm","장애 등록"],["…2.1.15.0.2","Cabinet alarm resume","장애 복구"],["…2.1.2.0.99","ACB group alarm","그룹 장애 등록"],["…2.1.2.0.100","ACB group alarm resume","그룹 장애 복구"]],[3300,2400,2900]))
    P(para("9.3 알람 처리 규칙",style="Heading2"))
    for x in ["snmpTrapOID.0을 기준으로 알람/복구 유형을 결정한다.","ordinal, alarm 문자열, level, equip ID/name, parent name을 varBind prefix로 추출한다.","장애이면 fault table 추가, 모듈/랙 점멸, 요약 알람, 팝업 및 설정된 등급의 음향을 수행한다.","복구이면 동일 모듈/셀 장애를 제거하고 남은 장애 유무에 따라 점멸을 해제한다.","Trap log는 최대 MAX_TRAP_LOG=1,000건으로 제한한다.","FAULT_ALARMS는 Board hardware fault 및 Cell 1~15 Fault를 셀 장애 상세 처리 대상으로 정의한다."] : P(bullet(x))
    P(para("9.4 과부하 방지",style="Heading2")); P(para("Trap 수신 큐는 deque(maxlen=2000)이며 가득 찰 경우 가장 오래된 항목이 제거된다. UI 로그도 1,000건으로 제한된다. 다만 폭주 시 유실 건수/드롭 카운터가 별도로 기록되지 않으므로 운영 모니터링 개선 항목으로 관리한다."))

    P(para("10. Master/Slave 연동 설계",style="Heading1"))
    P(para("10.1 역할 판정",style="Heading2")); P(para("QLockFile(app.lock)을 100ms 내 획득한 최초 인스턴스는 Master 후보가 되고, 획득하지 못한 추가 인스턴스는 forced_slave=True가 된다. ProfileDialog는 이를 반영하여 모드 선택을 제한한다."))
    P(para("10.2 등록 및 중계",style="Heading2"))
    P(table(["단계","Master","Slave"],[["1. 기동","UDP 50000 등록 listener 시작","사용 가능한 localhost Trap 포트 탐색"],["2. 등록","register JSON 수신 후 slave_targets 저장","프로파일/로컬 포트를 register JSON으로 전송"],["3. Trap","외부 UDP 162 Trap 수신","LocalTrapReceiver 대기"],["4. 중계","trap_data에 source IP 포함, 각 Slave 포트로 JSON UDP 송신","JSON decode 후 handle_trap 호출"],["5. 변경/종료","대상 목록 갱신/삭제","포트 변경 시 재등록, 종료 시 unregister"]],[1300,3700,3700]))
    P(para("10.3 장애 고려",style="Heading2")); P(para("UDP 기반이므로 등록/Trap 전달의 전달 보장이 없다. Slave 대상은 프로파일 정보로 재구성하며, 송신 실패는 대상별 예외로 격리한다. 강한 전달 보장이 필요하면 sequence, heartbeat, ACK/retry를 추가해야 한다."))

    P(para("11. EPO 차단/복구 설계",style="Heading1"))
    P(image_para("rIdImg4", 5300000, 5120000, "epo_flow")); P(para("그림 11-1. EPO 작업 흐름",size=17,color="666666",align="center"))
    P(para("11.1 OID와 명령값",style="Heading2")); P(table(["항목","OID","값"],[["EPO 준비","1.3.6.1.4.1.2011.6.164.1.2.2.1.1.11.1","1"],["모듈 출력","1.3.6.1.4.1.2011.6.164.1.18.3.1.2.{row_index}","차단 2 / 복구 1"]],[2000,4900,1700]))
    P(para("11.2 개별 작업",style="Heading2")); P(para("운영자 확인 후 대상 모듈의 row_index를 조회하고 EpoCutoffThread를 시작한다. 준비 OID SET/검증 성공 후 모듈 OID를 SET/검증한다. 결과에 따라 버튼 문구와 색상, 작업 잠금, 성공/실패 팝업을 갱신한다."))
    P(para("11.3 전체 작업",style="Heading2")); P(para("현재 alive 모듈 목록을 구한 뒤 큐에 저장하여 한 번에 하나씩 순차 실행한다. 모듈별 진행률과 결과를 갱신하고 실패 목록은 누적하되 다음 모듈은 계속 처리한다. 전체 완료 시 성공 수와 실패 수를 표시한다. 이 순차 설계는 장비에 동시에 다수 SET이 들어가는 것을 방지한다."))
    P(para("11.4 안전 요구",style="Heading2"))
    for x in ["차단과 복구 모두 명시적 확인 대화상자를 거친다.","연결되지 않았거나 대상 row_index가 없으면 명령을 실행하지 않는다.","SET 반환값이 요청값과 다르면 실패로 처리한다.","진행 중 중복 버튼 입력을 차단하고 종료 시 작업 스레드를 정리한다.","현장 적용 전 장비 제조사 MIB에서 명령값, 준비 절차, 재시도 안전성을 검증한다."] : P(bullet(x))

    P(para("12. 운전 데이터 기록 설계",style="Heading1"))
    P(para("12.1 동작",style="Heading2")); P(para("운영자가 기록 간격, 기간(1~30일), 필드 그룹을 선택한다. 시작 시 예상 용량과 디스크 여유 공간을 비교하고 충분할 때만 OperationDataRecordThread와 QTimer를 시작한다. 시작 직후 한 번 기록하며 이후 설정 간격마다 스냅샷을 queue에 넣는다. 날짜가 바뀌면 동일 session ID를 유지하고 날짜별 XLSX 파일을 사용한다."))
    P(para("12.2 선택 필드",style="Heading2")); P(table(["그룹","열"],[["equipment","Row Index, Equip ID, 모델, Barcode"],["voltage/current","모듈 전압[V], 모듈 전류[A]"],["soc_soh","SOC[%], SOH[%]"],["status/alarm","상태 코드/문자열, 알람"],["cell_summary","셀 최대/최소 전압"],["cell_detail","Cell 1~15 전압"],["temp_summary","최대/최소 온도"],["temp_detail","Cell 1~15 온도"],["epo","차단 버튼의 현재 상태 문자열"]],[2500,6100]))
    P(para("12.3 파일 규칙",style="Heading2")); P(para("파일명은 Operation_data_{기록시작일}_{기록시작시각}_{세션식별자}_{실제기록일}.xlsx 형식이다. 워크시트는 헤더 스타일, 고정 열, 중앙 정렬 등을 초기화하고 동일 날짜 파일이 있으면 load_workbook으로 이어 쓴다. 저장 성공 시 경로와 행 수를 UI에 표시하며 오류는 error_signal로 전달한다."))
    P(para("12.4 기록 종료",style="Heading2")); P(para("설정 종료시각을 30초 타이머로 확인하고 마지막 스냅샷을 넣은 뒤 기록을 중지한다. 수동 종료 또는 프로그램 종료 시 두 타이머를 제거하고 writer thread의 queue 종료 신호를 처리하며 최대 10초 기다린다."))

    P(para("13. UI 상세 설계",style="Heading1"))
    P(table(["영역/화면","구성","동작"],[["Header","로고, 앱명/버전, 시각, 시스템 자원","현재 시간 및 CPU/메모리 갱신"],["Connection panel","사이트/시스템/IP/포트/community, 접속 버튼","프로파일 저장, Enter 접속, Ping/SNMP 시작"],["Summary","전압·전류·SOC·SOH·상태, 제한 설정","상태 색상, 알람 강조, 설정 팝업"],["Module tables","좌 1~5 / 우 6~10, 측정값·알람·EPO","행 선택 상세, 순서 반영, 차단/복구"],["Fault table","번호, 모듈/셀, 전압/온도 등","Trap 장애 추가/복구 제거, 번호 재정렬"],["Alarm popup/log","최근 알람 및 전체 목록","등급별 음향, 점멸, 로그 삭제"],["Module detail","셀 1~15 전압/온도와 모듈 정보","주기적으로 module_data를 읽어 갱신"],["Operation record","간격/기간/필드/예상용량/상태","기록 시작·중지"]],[1800,3000,3800]))
    P(para("13.1 상태 표현",style="Heading2")); P(table(["상태","표현 원칙"],[["정상","녹색 계열 배경"],["경보","주황 계열 강조"],["차단/중대 장애","빨강 배경과 흰색 글자"],["통신 실패/미수집","Unknown 또는 '-'와 비활성 상태"],["활성 통신","Tx/Rx LED를 일정 시간 켠 뒤 타이머로 해제"],["랙/모듈 장애","주기적 점멸, 남은 장애가 없을 때 해제"]],[2200,6400]))
    P(para("13.2 사용성 규칙",style="Heading2"))
    for x in ["긴 식별 문자열은 line edit의 전체 텍스트 보기/툴팁을 지원한다.","초기 데이터 수집 중 진행 메시지를 표시하고 완료 또는 실패 시 닫는다.","짧은 안내는 자동 종료 메시지를 사용하여 반복 조작을 방해하지 않는다.","위험 명령은 확인 팝업, 작업 중 비활성화, 결과 팝업의 3단계 피드백을 제공한다."] : P(bullet(x))

    P(para("14. 예외·복구·성능·보안 설계",style="Heading1"))
    P(para("14.1 예외 및 복구",style="Heading2")); P(table(["상황","처리"],[["Ping timeout","False 반환, 접속 실패 UI"],["SNMP timeout/errorStatus","실패 Signal과 안내, 상태 초기화"],["Trap bind 실패","listener_status_signal(False,error), 포트 점유 가이드"],["UDP recv 종료","socket.close 후 OSError를 정상 종료로 간주"],["프로파일 오류","사용자 경고 또는 기본값 적용"],["Excel 저장 오류","error_signal, 기록 상태 빨강 표시"],["스레드 종료 지연","제한 시간 wait 후 경고 로그"],["Trap 폭주","고정 길이 deque/log로 메모리 상한 유지"]],[2700,5900]))
    P(para("14.2 성능",style="Heading2"))
    for x in ["네트워크 I/O와 파일 I/O는 UI 스레드 외부에서 수행한다.","SNMP는 관련 subtree를 bulkCmd로 수집해 요청 횟수를 줄인다.","운전 기록은 queue로 비동기 저장하며 UI는 데이터 스냅샷만 생성한다.","모듈 수는 화면/자료구조상 최대 10개, 셀/온도는 모듈당 최대 15개를 전제로 한다.","Trap 큐 2,000건과 로그 1,000건으로 메모리 증가를 제한한다."] : P(bullet(x))
    P(para("14.3 보안",style="Heading2")); P(para("현재 SNMPv2c는 community 문자열이 평문이며 인증·암호화가 없다. 프로파일 및 소스 주석의 community 노출, UDP spoofing, 무인증 localhost 중계 가능성을 고려해야 한다. 운영망 분리, 방화벽 allowlist, 파일 ACL, 로그 마스킹을 적용하고 가능한 경우 SNMPv3로 전환한다. 본 문서에는 코드에 존재하는 실제 community 값을 의도적으로 기재하지 않았다."))
    P(para("14.4 알려진 제약",style="Heading2"))
    for x in ["단일 파일에 UI, 통신, 도메인 로직, 저장소가 결합되어 변경 영향 범위가 크다.","일부 bare except와 print 기반 디버깅은 장애 원인 추적을 제한한다.","UDP Master/Slave 중계에 ACK, 순서번호, 무결성 검증이 없다.","고정 OID와 상태 코드가 코드에 직접 포함되어 MIB 변경 대응이 어렵다.","Trap queue overflow가 조용히 오래된 데이터를 제거한다."] : P(bullet(x))

    P(para("15. 시험 설계 및 추적성",style="Heading1"))
    tests=[
        ["TC-01","최초 인스턴스 시작","Master 가능, lock 유지, 프로파일 선택"],
        ["TC-02","동일 프로그램 추가 시작","forced Slave, Master 프로파일 선택 방지"],
        ["TC-03","정상 IP 접속","Ping 성공 후 SNMP 초기 load 완료"],
        ["TC-04","잘못된 IP/community","timeout 후 실패 안내 및 UI 초기화"],
        ["TC-05","UDP 162 선점","Trap bind 실패 팝업에 원인/조치 표시"],
        ["TC-06","정상 Polling 데이터","10개 모듈 매핑 및 단위/상태 표시"],
        ["TC-07","장애 Trap","로그/표/팝업/음향/점멸 동작"],
        ["TC-08","복구 Trap","해당 장애 제거, 남은 장애에 따른 점멸 유지/해제"],
        ["TC-09","Trap 폭주","UI 무응답 없음, 큐/로그 상한 유지"],
        ["TC-10","Slave 등록/포트 변경","대상 갱신, Trap 전달 및 수신"],
        ["TC-11","개별 차단/복구","준비→대상 SET 순서, 반환값 검증, UI 반영"],
        ["TC-12","전체 차단 중 일부 실패","후속 모듈 계속, 성공/실패 집계"],
        ["TC-13","기록 시작/일자 전환","즉시 기록, 날짜별 파일, 헤더/행 검증"],
        ["TC-14","디스크 공간 부족","기록 시작 차단 및 필요/가용 용량 안내"],
        ["TC-15","종료 중 Trap/기록 동작","모든 스레드·소켓·타이머 정상 종료"],
    ]
    P(table(["ID","시험 시나리오","기대 결과"],tests,[1100,3100,4500]))
    P(para("15.1 요구 기능 추적",style="Heading2")); P(table(["기능","주요 구현","시험"],[["상태 감시","SNMPThread / handle_snmp_result","TC-03,04,06"],["Trap 알람","SNMPTrapThread / handle_trap / handle_fault_trap","TC-05,07,08,09"],["다중 인스턴스","QLockFile / SlaveRegisterThread / LocalTrapReceiver","TC-01,02,10"],["EPO","EpoCutoffThread / full cutoff queue","TC-11,12"],["운전 기록","OperationDataRecordThread / record timers","TC-13,14"],["안전 종료","closeEvent / 각 stop 메서드","TC-15"]],[2200,4200,2200]))

    P(para("부록 A. 주요 OID 목록",style="Heading1"))
    oidrows=[
        ["sysUpTime","1.3.6.1.2.1.1.3.0","접속/기본 응답 확인"],
        ["Trap 재전송","1.3.6.1.4.1.2011.6.164.1.1.2.4.0","SET 1"],
        ["EPO 준비","1.3.6.1.4.1.2011.6.164.1.2.2.1.1.11.1","SET 1"],
        ["모듈 차단/복구","1.3.6.1.4.1.2011.6.164.1.18.3.1.2.{row}","SET 2/1"],
        ["SOC 제한 Enable","1.3.6.1.4.1.2011.6.164.1.17.2.1.29.96","GET/SET"],
        ["SOC 제한값","1.3.6.1.4.1.2011.6.164.1.17.2.1.30.96","GET/SET"],
        ["충전 전류 제한","1.3.6.1.4.1.2011.6.164.1.17.2.1.13.96","GET/SET"],
        ["장비 ID","…1.18.1.1.2.{row}","모듈 매핑"],
        ["장비 주소","…1.18.1.1.4.{row}","모듈 매핑"],
        ["SW 버전","…1.18.1.1.5.{row}","장비 정보"],
        ["모델","…1.18.1.1.12.{row}","장비 정보"],
        ["바코드","…1.18.1.1.13.{row}","불일치 검사"],
        ["snmpTrapOID.0","1.3.6.1.6.3.1.1.4.1.0","Trap 유형"],
    ]
    P(table(["명칭","OID","용도"],oidrows,[2300,4700,1700]))
    P(para("※ ‘…’ 표기는 공통 prefix 1.3.6.1.4.1.2011.6.164을 생략한 것이다. 정확한 데이터 형식·배율·허용값은 제조사 MIB를 최종 기준으로 검증한다.",size=17,color="666666"))

    P(para("부록 B. 유지보수 권고",style="Heading1"))
    P(table(["우선순위","개선 항목","효과"],[["높음","community를 OS 보안 저장소/암호화 설정으로 분리하고 로그 마스킹","자격정보 노출 감소"],["높음","EPO 명령에 감사 로그(사용자/시각/대상/결과)와 현장 권한 제어 추가","안전성과 추적성 향상"],["높음","MIB/OID/배율/상태 코드를 별도 schema 모듈로 분리","장비 버전 변경 대응"],["중간","BatteryMonitorUI를 view/service/repository로 분리","테스트성과 변경 영향 개선"],["중간","logging 모듈과 회전 파일 로그, 예외 traceback 도입","장애 분석 개선"],["중간","Master/Slave heartbeat, sequence, ACK/retry, 메시지 schema version 추가","중계 신뢰성 향상"],["중간","Trap drop counter와 rate limit/배치 UI 갱신 추가","폭주 가시성·응답성 향상"],["낮음","pytest 기반 OID parser/상태변환/파일명/용량계산 단위시험","회귀 방지"]],[1200,4800,2700]))
    P(para("설계 근거 및 검토 주의",style="Heading2")); P(para("이 문서는 TBC1000B_감시프로그램_V3.2.3.py의 정적 구조, 클래스/메서드, 상수 및 OID 사용을 근거로 역설계하였다. 코드에서 확정할 수 없는 장비 측 프로토콜 의미는 ‘제조사 MIB 확인 필요’로 취급한다. 배포 전에는 실제 장비, 네트워크, 방화벽, 다중 인스턴스 환경에서 본 문서의 시험 항목을 수행하고 승인 이력에 결과를 반영한다."))

    sect='''<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader1"/><w:footerReference w:type="default" r:id="rIdFooter1"/><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1100" w:right="1000" w:bottom="1000" w:left="1000" w:header="500" w:footer="500"/><w:cols w:space="708"/><w:docGrid w:linePitch="360"/></w:sectPr>'''
    return ''.join(parts)+sect


def make_docx(diagrams):
    body=build_document(diagrams)
    ns='xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
    document=f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {ns}><w:body>{body}</w:body></w:document>'
    styles='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="맑은 고딕" w:hAnsi="맑은 고딕" w:eastAsia="맑은 고딕"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="400" w:after="180"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="1F4E78"/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="260" w:after="120"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="2F75B5"/><w:sz w:val="25"/><w:szCs w:val="25"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/></w:pPr></w:style><w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="A6A6A6"/><w:left w:val="single" w:sz="4" w:color="A6A6A6"/><w:bottom w:val="single" w:sz="4" w:color="A6A6A6"/><w:right w:val="single" w:sz="4" w:color="A6A6A6"/><w:insideH w:val="single" w:sz="4" w:color="D0D0D0"/><w:insideV w:val="single" w:sz="4" w:color="D0D0D0"/></w:tblBorders><w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style></w:styles>'''
    numbering='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="360"/></w:tabs><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'''
    rels=['''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/><Relationship Id="rIdHeader1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/><Relationship Id="rIdFooter1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>''']
    for i in range(4): rels.append(f'<Relationship Id="rIdImg{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image{i+1}.png"/>')
    rels.append('</Relationships>'); rels=''.join(rels)
    header='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="right"/><w:pBdr><w:bottom w:val="single" w:sz="4" w:color="9EADBA"/></w:pBdr></w:pPr>'''+xrun('TBC1000B 감시프로그램 v3.2.3 | 개발 상세 설계서',False,16,'5A6B7A')+'</w:p></w:hdr>'
    footer='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'''+xrun('내부 검토용  |  ',False,15,'777777')+'''<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText>PAGE</w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>'''
    content_types='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/><Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>'''
    root_rels='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    with ZipFile(OUT,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',content_types); z.writestr('_rels/.rels',root_rels)
        z.writestr('word/document.xml',document); z.writestr('word/styles.xml',styles); z.writestr('word/numbering.xml',numbering)
        z.writestr('word/_rels/document.xml.rels',rels); z.writestr('word/header1.xml',header); z.writestr('word/footer1.xml',footer)
        for i,p in enumerate(diagrams,1): z.write(p,f'word/media/image{i}.png')


if __name__ == '__main__':
    assert SOURCE.exists()
    diagrams=save_diagrams(); make_docx(diagrams)
    print(OUT)
    print(OUT.stat().st_size)
