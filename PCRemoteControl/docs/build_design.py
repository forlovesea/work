"""Rebuild the Korean detailed design document with python-docx."""
from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent
d = Document()
s = d.sections[0]
s.page_width, s.page_height = Cm(21), Cm(29.7)
s.top_margin = s.bottom_margin = Cm(1.8)
s.left_margin = s.right_margin = Cm(2)
for name in ('Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2'):
    style = d.styles[name]
    style.font.name = '맑은 고딕'
    style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '맑은 고딕')
    style.font.color.rgb = RGBColor(0, 0, 0)
d.styles['Normal'].font.size = Pt(10)
d.styles['Normal'].paragraph_format.space_after = Pt(7)
d.styles['Normal'].paragraph_format.line_spacing = 1.12
d.styles['Title'].font.size = Pt(26)
d.styles['Heading 1'].font.size = Pt(18)
d.styles['Heading 2'].font.size = Pt(12)
footer = s.footer.paragraphs[0]
footer.alignment = 2
footer.add_run('PCRemoteControl v0.1.2  |  ')
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); footer._p.append(field)
d.core_properties.title = 'PCRemoteControl 개발 상세 설계서'
d.core_properties.subject = 'Windows 원격제어 클라이언트와 Python TLS Relay 구현 설계'
d.core_properties.author = 'PCRemoteControl'

def p(text): d.add_paragraph(text)
def h(text): d.add_heading(text, 2)
def page(title): d.add_page_break(); d.add_heading(title, 1)
def code(text):
    for line in text.splitlines():
        z = d.add_paragraph(); z.paragraph_format.space_after = Pt(1)
        z.paragraph_format.line_spacing = 1
        r = z.add_run(line); r.font.name = 'Consolas'; r.font.size = Pt(8)
def table(headers, rows, widths=None):
    t = d.add_table(rows=1, cols=len(headers)); t.autofit = False
    if widths is None: widths = [17 / len(headers)] * len(headers)
    for c, w in zip(t.columns, widths): c.width = Cm(w)
    for c, v in zip(t.rows[0].cells, headers): c.text = v
    for row in rows:
        for c, v in zip(t.add_row().cells, row): c.text = str(v)
    t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
    for i, row in enumerate(t.rows):
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for c, w in zip(row.cells, widths):
            c.width = Cm(w)
            for para in c.paragraphs:
                para.paragraph_format.space_after = Pt(5)
                para.paragraph_format.space_before = Pt(4)
                for r in para.runs: r.font.size = Pt(9); r.bold = i == 0
            if i == 0:
                shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), 'E8EDF3'); c._tc.get_or_add_tcPr().append(shade)
    d.add_paragraph().paragraph_format.space_after = Pt(1)

d.add_paragraph('PCRemoteControl\n개발 상세 설계서', 'Title')
d.add_paragraph('Windows HOST TARGET 및 TLS Relay', 'Subtitle')
p('문서 버전 1.0  |  제품 버전 v0.1.2  |  작성일 2026년 11월 10일')
p('이 문서는 유지보수 개발자와 서버 운영자를 위해 현재 구현의 구성, 인증 절차, 메시지 규격, 상태 전이, UI 동작과 배포 절차를 정의한다. 비밀번호와 이메일 인증을 모두 통과한 연결만 원격 화면 조회와 입력 제어를 사용할 수 있다.')
h('설계 범위')
p('Windows 10 및 11의 로그인된 데스크톱에서 HOST가 TARGET의 주 모니터를 조회하고 키보드와 마우스를 제어한다. 두 PC는 외부 TLS Relay에 접속한다. 서버는 Python 표준 라이브러리로 구현되며, 선택 기능인 Watchdog가 TARGET 프로세스 복구를 담당한다.')
table(['구분', '내용'], [
('v0.1.2 변경', 'VS Code 계열 다크 스타일, 비밀번호 눈 버튼, 전체화면 안내 팝업, 상세 설계서 및 압축 단일 실행 파일 배포'),
('인증', '공유 비밀번호 확인 후 forlovesea@gmail.com으로 6자리 코드 발송 및 검증'),
('배포', 'Windows x64 단일 EXE와 Ubuntu systemd Relay 서비스'),
('중요 제약', '재접속 시 이메일 재인증 필요. 주 모니터만 지원. Relay가 화면과 입력을 복호화한다.')], [3,14])
h('문서 구성')
p('2장 구성 및 책임 · 3장 인증 · 4장 프로토콜 · 5장 상태와 오류 · 6장 화면 및 입력 · 7장 UI · 8장 저장 및 복구 · 9장 서버 운영 · 10장 빌드 및 검증')
h('설계 근거')
p('Client의 MainForm, Connection, Desktop, TargetRecovery, EmailVerificationDialog, FullscreenHintDialog와 Watchdog, server/relay.py 및 테스트 코드를 기준으로 작성한다. 운영 서버의 실제 SMTP 성공과 원격 두 PC 간 실사용 검증은 배포 후 별도 수행한다.')

page('2 시스템 구성과 모듈 책임')
code('Windows HOST -- TLS TCP 61000 --> Python Relay <-- TLS TCP 61000 -- Windows TARGET\n                                      |\n                                SMTP STARTTLS\n                                      |\n                              forlovesea@gmail.com')
p('HOST와 TARGET은 모두 서버로 나가는 연결을 사용한다. 일반적인 NAT 환경에서 TARGET 자체의 인바운드 포트 개방은 필요하지 않다. Relay 서버가 공유기 뒤에 있으면 해당 서버로 TCP 61000 포트포워딩이 필요하다.')
table(['파일', '주요 책임'], [
('Client/Program.cs', 'STA UI 실행, --target / --auto-connect / --watchdog-dir 처리, --target 실행 시 로컬 Mutex'),
('Client/MainForm.cs', '연결 수명주기, UI 상태, TARGET 목록, 세션 연결, 화면 캡처 타이머와 입력 전달'),
('Client/Connection.cs', 'TcpClient와 SslStream, 인증서 검증, 길이 프레이밍, 인증 응답과 코드 제출'),
('Client/Desktop.cs', '주 모니터 JPEG 캡처, 좌표 변환, Win32 SendInput, 눌린 키 해제'),
('Client/TargetRecovery.cs', '현재 Windows 사용자 범위 DPAPI를 사용한 TARGET 비밀번호 보관'),
('Client/DarkTheme.cs', '짙은 회색 배경, Segoe UI 10pt, 파란 강조색, 평면 버튼과 TARGET 목록 렌더링'),
('Client의 두 Dialog', '이메일 코드 입력 및 전체화면 진입 안내'),
('server/relay.py', '접속 제한, 비밀번호 및 이메일 인증, TARGET 등록, HOST와 TARGET 연결 및 중계'),
('Watchdog', '별도 선택 프로그램. 자신이 시작한 TARGET의 종료와 UI 응답 지연 감지')], [5,12])
h('동시성과 소유권')
p('클라이언트 UI는 WinForms 메시지 루프에서 갱신한다. 캡처 작업은 Task.Run으로 수행하고 sendingFrame으로 중복 실행을 방지한다. 소켓 송신은 SemaphoreSlim으로 직렬화한다. 서버는 asyncio 이벤트 루프와 Peer별 송신 Lock을 사용한다. SMTP의 동기 호출은 executor에서 실행한다.')

page('3 비밀번호와 이메일 인증 설계')
table(['순서', '처리'], [
('1 TLS', '클라이언트는 서버 이름과 인증서 체인을 검증한 뒤 hello를 전송한다. 인증용 소켓 연결과 서비스 이용 허가는 구분한다.'),
('2 비밀번호', '서버가 문자열 타입을 검사하고 hmac.compare_digest로 비교한다. 실패하면 error를 보내고 닫는다.'),
('3 발송 제한', '잘못된 비밀번호는 IP별 60초 창에서 10회 제한. 이메일은 IP당 60초 1회, 전체 최소 5초 간격으로 제한한다.'),
('4 메일 발송', 'secrets.randbelow로 000000부터 999999까지 생성한다. 고정 수신자에게 SMTP STARTTLS로 전달한다.'),
('5 입력 요청', '성공하면 email_required와 expires_in 300을 전송한다. 클라이언트는 6자리 숫자만 확인 버튼을 활성화한다.'),
('6 검증', '같은 연결에서 verify_email 한 번을 받는다. 코드 일치 시 TARGET을 등록하고 ok를 반환한다.'),
('7 서비스 시작', 'ok 수신 후 heartbeat, 목록 갱신, 캡처 타이머를 시작한다. HOST는 list를 요청한다.')], [2.5,14.5])
h('실패와 만료')
p('SMTP 설정 누락 또는 발송 실패 시 인증을 허용하지 않는다. 발송 작업의 서버 대기는 최대 25초, SMTP 소켓 타임아웃은 15초이다. 서버는 email_required 이후 300초 동안 검증 메시지를 기다린다. 클라이언트 입력 대기는 295초로 제한한다. 오입력, 다른 종류의 메시지 또는 만료는 연결 종료로 처리한다.')
p('코드는 해당 연결의 지역 변수에만 존재하며 파일이나 로그에 보관하지 않는다. 성공한 코드로 다른 연결을 인증할 수 없다. 연결 종료 후에는 새 코드가 필요하다. 재인증을 생략하는 신뢰 기기나 장기 토큰은 구현하지 않는다.')
h('메일 설정과 고정 수신자')
p('발송 계정과 수신자는 서로 다를 수 있다. PCREMOTE_SMTP_HOST, PORT, USER, PASSWORD, FROM을 서버 환경 파일에서 읽는다. FROM 생략 시 USER를 사용하며 PORT 기본값은 587이다. 현재 STARTTLS만 지원하고 SSL 465 방식과 PHP mail 대체 경로는 지원하지 않는다.')

page('4 통신 프레임과 메시지 규격')
p('모든 메시지는 4바이트 unsigned big endian 길이 헤더와 UTF-8 JSON 객체로 구성한다. 길이는 헤더를 제외한 JSON 바이트 수이며 1부터 8 MiB까지 허용한다. 배열 등 객체가 아닌 JSON은 거절한다. 이미지 byte[]는 JSON에서 Base64 문자열로 표현된다.')
table(['type', '방향', '주요 필드와 의미'], [
('hello', 'PC → 서버', 'role host 또는 target, password, id, name'),
('email_required', '서버 → PC', 'email 고정 수신자, expires_in 300'),
('verify_email', 'PC → 서버', 'code 6자리 문자열'),
('ok / error', '서버 → PC', '인증 성공 / 실패 또는 서비스 오류 message'),
('ping / pong', 'PC ↔ 서버', '인증 이후 연결 유지'),
('list / targets', 'HOST ↔ 서버', 'targets 배열: id, name, state ready 또는 busy'),
('connect / paired', 'HOST → 서버 → 양측', 'connect.id로 선택. HOST의 paired에는 name 포함'),
('disconnect / ended', 'PC → 서버 → 양측', '짝 연결 해제. 서버 연결은 유지'),
('frame', 'TARGET → HOST', 'data: JPEG Base64. 서버가 짝 HOST로 중계'),
('input', 'HOST → TARGET', 'action key, mouse, release. 서버가 짝 TARGET으로 중계')], [3.2,4,9.8])
h('입력 메시지 예시')
code('{"type":"input","action":"key","key":65,"down":true}\n{"type":"input","action":"mouse","x":0.5,"y":0.5,"button":"left","down":true}\n{"type":"input","action":"release"}')
h('검증 및 제한')
p('TARGET id와 name은 각각 길이 1~80의 문자열이다. 같은 id가 이미 등록되어 있으면 거절한다. 연결된 Peer는 최대 256개이며 인증 대기 중인 연결도 포함한다. HOST와 TARGET은 각각 하나의 상대만 연결할 수 있다. 존재하지 않거나 사용 중인 TARGET에는 error를 반환한다.')

page('5 연결 상태와 오류 복구')
table(['상태', '진입 조건', '종료 및 다음 상태'], [
('중지', '앱 시작 또는 사용자의 연결 중지', '서버 연결 클릭 → TLS 및 인증'),
('인증 중', 'running=true, 편집 컨트롤 비활성화', '이메일 코드 확인 → 인증 대기 해제'),
('연결 대기', 'ok 수신, connection 지정', 'HOST connect 성공 → 원격제어'),
('원격제어', 'paired 수신, paired=true', 'disconnect / ended / 연결 끊김 → 세션 종료'),
('재시도', 'TARGET의 일반 통신 예외', '5초 후 새 TLS 연결 및 새 이메일 인증'),
('인증 중단', 'LoginException 또는 인증창 취소', 'lifetime 취소, health paused. 수동 서버 연결 필요')], [3,6,8])
h('시간 제한과 주기')
table(['항목', '설정'], [
('TCP TLS 초기 연결', '클라이언트 15초. 서버 TLS handshake 10초'),
('hello / 일반 메시지 수신', '서버 hello 10초. 일반 메시지 양측 35초'),
('메시지 송신', '10초 제한. 느린 상대에게 무한 대기하지 않음'),
('유지 및 목록', 'ping 10초, HOST 목록 갱신 5초'),
('TARGET 캡처', '125ms 주기. 처리 속도에 따라 실제 FPS는 더 낮음'),
('마우스 이동', '마지막 전송 이후 35ms보다 긴 경우 전송')], [6,11])
h('종료 정리')
p('서버 finally에서 TARGET 등록을 제거하고 짝 상대에 ended를 전달한다. 클라이언트는 연결을 비우고 heartbeat, listing, capture를 중지한다. EndSession은 화면 이미지 자원을 해제하고 TARGET에서 눌린 키와 버튼을 해제한다. disconnect 후 늦게 도착한 frame과 input은 서버에서 버린다.')
p('일반 서버 오류 메시지는 상태 표시줄에 표시된다. 인증 실패는 자동 재시도를 멈춘다. SMTP 작업의 wait_for 취소가 이미 실행 중인 동기 메일 스레드까지 즉시 종료시키는 것은 아니므로, 늦게 도착한 코드는 해당 연결이 종료되었다면 사용할 수 없다.')

page('6 화면 전송과 원격 입력')
h('화면 캡처')
p('Desktop.Capture는 Screen.PrimaryScreen의 전체 영역을 CopyFromScreen으로 읽는다. 가로 최대 1600픽셀까지 비율을 유지해 축소하며 더 작은 화면은 확대하지 않는다. JPEG 품질은 65이다. 압축 데이터를 JSON Base64로 보내므로 원본 바이너리보다 전송 크기가 증가한다.')
p('HOST는 PictureBox Zoom으로 수신 이미지를 표시한다. 다음 이미지로 교체할 때 이전 Image를 Dispose한다. 캡처 작업이 끝나기 전에 연결이나 짝 상태가 바뀌면 해당 결과를 보내지 않는다. 오디오, 파일 전송, 클립보드 동기화와 다중 모니터 선택은 구현 범위 밖이다.')
h('좌표 변환')
code('scale = min(viewWidth / imageWidth, viewHeight / imageHeight)\nimageDisplayWidth = imageWidth * scale\nx = (mouseX - (viewWidth - imageDisplayWidth) / 2) / imageDisplayWidth\ny = (mouseY - (viewHeight - imageHeight * scale) / 2) / (imageHeight * scale)')
p('여백을 제외한 이미지 영역을 0~1 좌표로 변환한다. TARGET은 이를 주 모니터 픽셀로 복원하고 Windows 가상 화면 기준 0~65535 절대 좌표로 변환한다. NaN 및 무한값은 무시하고 좌표는 경계로 제한한다.')
table(['입력', '처리'], [
('키보드', '가상 키 코드 1~254만 허용. key down 및 up 전송. 일부 확장 키 플래그 적용'),
('마우스', '왼쪽, 오른쪽, 가운데 버튼과 이동, 휠 지원. 휠 값은 -1200~1200으로 제한'),
('포커스', 'HOST의 원격 화면이 포커스를 가진 경우만 CanInput=true'),
('해제', 'HOST 비활성화 또는 화면 포커스 상실 시 release 전송. TARGET은 추적 중인 키와 버튼을 해제'),
('권한 제한', 'SendInput은 Windows 권한 경계에 따라 관리자 창, 잠금 화면 등에서 차단될 수 있음')], [3,14])
h('성능 및 보안 경계')
p('고정 품질 JPEG와 TCP를 사용하는 구조이며 지연 적응형 비트레이트나 동영상 코덱은 없다. 화면은 TLS로 전송되지만 Relay에서 복호화되므로 종단간 암호화 시스템은 아니다. Relay 운영자는 신뢰 가능한 주체여야 한다.')

page('7 사용자 인터페이스 상세')
table(['요소', '동작'], [
('서버 주소와 포트', '기본 주소 61.105.141.21, 기본 포트 61000. 55000~60000은 기존 서비스 예약 범위로 거절'),
('HOST 및 TARGET', '일반 실행은 역할 선택 가능. --target 실행은 TARGET 역할 고정'),
('TARGET 이름', 'HOST 목록에 표시되는 PC 이름. 기본은 Environment.MachineName. TARGET 중지 상태에서 편집'),
('서버 연결과 연결 중지', '연결 시작 및 lifetime 취소. 연결 중지 시 원격제어도 종료'),
('목록과 원격접속', 'HOST에서 TARGET 선택 후 접속. 목록에 연결 가능 또는 사용 중 표시'),
('비밀번호 눈 버튼', '기본 숨김. 클릭 시 UseSystemPasswordChar를 반전. 표시 상태 저장 없음. 툴팁과 접근성 이름 갱신'),
('이메일 인증창', '고정 수신자 안내, 6자리 숫자 입력 검사, 확인 및 취소. 200ms 타이머로 취소와 만료 감지'),
('전체화면', 'HOST에서 버튼 또는 F11로 진입. 설정 및 목록 패널 숨김, 창 테두리 제거'),
('전체화면 안내', '진입마다 Esc 또는 F11 복귀 안내. 3초 자동 닫힘 또는 확인 버튼. 안내창에서도 Esc/F11로 복귀')], [3.5,13.5])
h('전체화면 상태 보존')
p('진입 직전 Bounds와 WindowState를 보관한다. 종료 시 Sizable 테두리와 이전 위치, 크기, 최대화 상태를 복원한다. 팝업은 소유 창 중앙의 모달 창이며 타이머로 닫힌다. 확인과 자동 닫힘은 전체화면을 유지하고 원격 화면으로 포커스를 돌린다. 팝업 키 입력은 원격 입력으로 전달하지 않는다.')
h('상태 표시의 의미')
p('TARGET 연결 유지 중은 이메일 인증과 TARGET 등록까지 완료되었음을 뜻한다. HOST 원격제어 중은 짝 연결 완료 상태이다. 원격접속 종료 후 서버 연결 유지 중이면 다시 HOST를 기다린다. 서버의 TCP established만으로 이메일 인증 완료 여부를 판별할 수는 없다.')
h('자원 해제')
p('폼 종료 시 연결을 중지하고 heartbeat, 캡처, 목록, health 타이머와 이미지, ToolTip을 해제한다. 각 팝업은 자체 타이머를 Dispose한다. 전체화면 안내 종료 후 부모 창이 이미 폐기되었다면 포커스 복원을 수행하지 않는다.')

page('8 로컬 저장과 TARGET 자동 복구')
table(['저장 위치', '내용 및 보호'], [
('%LOCALAPPDATA%/PCRemoteControl/settings.json', 'server, port, id, name. 일반 설정이며 비밀번호는 포함하지 않음'),
('같은 폴더의 target-password.bin', 'TARGET 비밀번호를 현재 Windows 사용자 DPAPI로 암호화. tmp 작성 후 교체'),
('같은 폴더의 watchdog.log', 'Watchdog 상태와 오류 기록. 512000바이트 초과 시 .old로 회전'),
('%TEMP%/PCRemoteControl-watchdog-임의값/health', 'running, paused, stopped 및 파일 수정 시각으로 UI 생존 여부 전달'),
('서버 메모리', 'targets, peers, 실패 횟수, 발송 제한 시각. 프로세스 재시작 시 초기화')], [8,9])
h('복구 정책')
p('Watchdog는 2초마다 확인한다. 자신이 실행한 TARGET에만 종료 권한을 행사하고 다른 TARGET을 인계하지 않는다. 시작 후 60초 유예와 60초 초과 heartbeat 지연을 모두 만족할 때 응답 없음으로 판단한다. 재시작 간격은 5, 10, 20, 40, 60초이며 5분 정상 동작 후 실패 횟수를 초기화한다.')
p('TARGET의 정상 종료 상태 stopped는 감시를 중지한다. paused 상태는 사용자의 중지 의도로 처리한다. 감시 창을 닫아도 이미 실행 중인 TARGET은 유지된다. 감시 중지는 원격 연결 차단 기능이 아니므로 즉시 차단하려면 TARGET의 연결 중지를 사용한다.')
h('중복 실행과 인수')
code('PCRemoteControl-v0.1.2.exe --target\nPCRemoteControl-v0.1.2.exe --target --auto-connect\nPCRemoteControl-v0.1.2.exe --target --auto-connect --watchdog-dir <folder>')
p('Program의 Local\\PCRemoteControl.Target Mutex는 --target 실행 경로에 적용된다. 일반 실행 후 UI에서 TARGET을 선택한 경우까지 전역 중복을 보장하지는 않는다. 서버의 동일 id 등록 거절은 별도로 작동한다.')
h('인증과 복구의 관계')
p('프로세스가 복구되거나 네트워크가 재연결되어도 이메일 인증을 다시 해야 한다. Watchdog는 인증을 우회하지 않는다. 단일 클라이언트 EXE에는 별도 Watchdog 실행 파일이 포함되지 않으며, 감시 기능 사용 시 선택 빌드로 생성한 Watchdog와 같은 버전 클라이언트를 함께 배치한다.')

page('9 서버 설치와 SMTP 운영')
h('설치 순서')
code('git clone https://github.com/forlovesea/work.git\ncd work/PCRemoteControl\npython3 -m unittest discover -s server -v\nsudo sh server/install.sh \\\n  /etc/letsencrypt/live/remotecontrol-ip/fullchain.pem \\\n  /etc/letsencrypt/live/remotecontrol-ip/privkey.pem')
p('인증서는 서버 주소의 SAN과 유효기간 및 신뢰 체인이 맞아야 한다. 설치기는 인증서 로드를 확인하고 61000 충돌을 검사한다. pcremote 그룹과 계정을 생성하고 /opt/pcremote/relay.py 및 systemd unit을 설치한다. 이전 서버 코드는 relay.py.previous로 남기며 기존 환경 파일은 보존한다.')
h('환경 파일')
code('# /etc/pcremote/relay.env\nPCREMOTE_PASSWORD="replace-with-shared-password"\nPCREMOTE_SMTP_HOST=smtp.gmail.com\nPCREMOTE_SMTP_PORT=587\nPCREMOTE_SMTP_USER=sender@example.com\nPCREMOTE_SMTP_PASSWORD="replace-with-smtp-credential"\nPCREMOTE_SMTP_FROM=sender@example.com')
p('기존 설치정보 앱은 /etc/installed-management/mail.php 또는 APP_MAIL_CONFIG 경로를 사용한다. WebConference의 /etc/moa/moa.env도 참고할 수 있다. SMTP_USERNAME을 PCREMOTE_SMTP_USER로 옮기며 나머지 발송 설정도 접두어에 맞게 옮긴다. 실제 비밀값은 저장소에 포함하지 않는다.')
h('서비스와 진단')
code('sudo chown root:pcremote /etc/pcremote/relay.env\nsudo chmod 640 /etc/pcremote/relay.env\nsudo systemctl restart pcremote-relay\nsudo systemctl status pcremote-relay --no-pager\nsudo journalctl -u pcremote-relay -n 50 --no-pager\nsudo ss -ltnp \'sport = :61000\'')
p('서비스는 비특권 계정, NoNewPrivileges, ProtectSystem=strict, ProtectHome, PrivateTmp, MemoryMax=512M 및 TasksMax=64를 사용한다. 인바운드 TCP 61000과 SMTP 서버로 나가는 통신이 필요하다. 서비스 파일이 없으면 설치부터 수행한다.')
p('인증서는 설치 시 /etc/pcremote로 복사한다. 원본 갱신만으로 복사본이 갱신되지 않는다. 갱신 후 설치기를 다시 실행하거나 별도 deploy hook에서 복사와 재시작을 처리해야 한다. 현재 저장소에는 해당 인증서 자동 반영 훅이 없다.')

page('10 빌드 검증과 유지보수')
h('버전과 산출물')
p('제품 버전은 v0.1.2, AssemblyVersion과 FileVersion은 0.1.2.0이다. Windows x64 자체 포함 단일 파일로 배포하며 압축 옵션을 사용한다. .NET Desktop Runtime을 별도로 설치하지 않아도 되지만 실행 중 내장 네이티브 라이브러리가 임시 경로로 추출될 수 있다.')
code('powershell -NoProfile -ExecutionPolicy Bypass -File .\\build.ps1\n# Optional watchdog build\npowershell -NoProfile -ExecutionPolicy Bypass -File .\\build.ps1 -IncludeWatchdog')
p('기본 산출물은 release/v0.1.2/PCRemoteControl-v0.1.2.exe 한 개와 SHA256SUMS-v0.1.2.txt이다. Watchdog는 선택 빌드이며 동일 폴더에 별도 실행 파일을 생성한다. 빌드 후 새 파일로 교체하려면 실행 중인 이전 프로그램을 먼저 종료한다.')
h('자동 검증')
table(['검증', '범위'], [
('server/test_relay.py 13개', '비밀번호 실패 무발송, 코드 검증 전 등록 금지, 코드 오입력과 선행 명령 거절, 재사용 거절, 만료, 발송 제한, SMTP 실패와 설정 누락, STARTTLS 및 고정 수신자, 중복 id, 짝 연결과 중계, 정리, 길이 제한'),
('RecoveryTests 7개', '재시작 지연 상한, 시작 유예, 정상 및 무응답 UI 판단, heartbeat 누락, DPAPI 암호화와 복호화'),
('컴파일', 'Client 및 선택 Watchdog의 Release 빌드, 버전 메타데이터와 산출물 해시 확인')], [4,13])
h('배포 후 인수 확인')
p('실제 SMTP 수신과 HOST 및 TARGET의 인증 성공, 잘못된 코드의 거절, 두 PC 간 화면 및 입력 전달, 연결 중지 시 제어 차단을 확인한다. 눈 버튼의 두 상태와 전체화면 팝업의 3초 자동 닫힘, 확인 버튼, Esc 및 F11 복귀도 실제 UI에서 확인한다. 자동 테스트는 SMTP를 모의 처리하며 실제 메일 전달을 보장하지 않는다.')
h('유지보수와 알려진 한계')
p('공유 비밀번호 구조로 사용자별 권한과 감사 추적은 없다. 기본 비밀번호는 운영 시 교체해야 한다. SMTP 상세 실패 원인을 별도 구조화 로그로 남기지 않는다. 서비스 상태가 정상이어도 메일 발송이나 실제 원격제어까지 정상이라는 뜻은 아니다. 무인 재접속, 코드 재발송 UI, 화면 해상도 적응, 다중 모니터, 인증서 자동 갱신 반영은 후속 개선 대상이다.')
p('변경 시 프로토콜 필드, 인증 완료 시점, 폐기 자원과 UI 스레드 접근을 함께 검토한다. 이전 이메일 인증 미지원 서버와 클라이언트는 호환되지 않으므로 양쪽을 함께 업데이트한다.')

output = ROOT / 'PCRemoteControl-v0.1.2-개발상세설계서.docx'
d.save(output)
print(output)
