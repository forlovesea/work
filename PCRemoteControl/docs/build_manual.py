"""Build the Korean operations manual with python-docx."""
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
    st = d.styles[name]
    st.font.name = '맑은 고딕'
    st.font.color.rgb = RGBColor(0, 0, 0)
    st.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '맑은 고딕')
d.styles['Normal'].font.size = Pt(10)
d.styles['Normal'].paragraph_format.space_after = Pt(7)
d.styles['Normal'].paragraph_format.line_spacing = 1.12
d.styles['Title'].font.size = Pt(25)
d.styles['Heading 1'].font.size = Pt(18)
d.styles['Heading 2'].font.size = Pt(12)
f = s.footer.paragraphs[0]
f.alignment = 2
f.add_run('PCRemoteControl  |  ')
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); f._p.append(field)

def p(text): d.add_paragraph(text)
def h(text): d.add_heading(text, 2)
def page(title): d.add_page_break(); d.add_heading(title, 1)
def code(text):
    for line in text.strip().splitlines():
        z = d.add_paragraph()
        z.paragraph_format.space_after = Pt(1)
        z.paragraph_format.line_spacing = 1.0
        r = z.add_run(line); r.font.name = 'Consolas'; r.font.size = Pt(8.5)
    d.add_paragraph().paragraph_format.space_after = Pt(2)
def table(headers, rows, widths):
    t = d.add_table(rows=1, cols=len(headers)); t.autofit = False
    for c, width in zip(t.columns, widths): c.width = Cm(width)
    for c, text in zip(t.rows[0].cells, headers): c.text = text
    for values in rows:
        for c, text in zip(t.add_row().cells, values): c.text = text
    for i, row in enumerate(t.rows):
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for c, width in zip(row.cells, widths):
            c.width = Cm(width); c.vertical_alignment = 1
            pr = c._tc.get_or_add_tcPr()
            borders = OxmlElement('w:tcBorders')
            for side in ('top', 'bottom', 'left', 'right'):
                e = OxmlElement('w:' + side); e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), '4'); e.set(qn('w:color'), 'D9D9D9'); borders.append(e)
            pr.append(borders)
            margins = OxmlElement('w:tcMar')
            for side in ('top','bottom','left','right'):
                e = OxmlElement('w:' + side); e.set(qn('w:w'), '100'); e.set(qn('w:type'), 'dxa'); margins.append(e)
            pr.append(margins)
            if i == 0:
                sh = OxmlElement('w:shd'); sh.set(qn('w:fill'), 'E7EEF5'); pr.append(sh)
            for par in c.paragraphs:
                par.paragraph_format.space_after = Pt(3)
                for r in par.runs: r.font.size = Pt(9); r.bold = i == 0
    t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
    d.add_paragraph().paragraph_format.space_after = Pt(2)

d.add_paragraph('PCRemoteControl 설치 실행 관리 매뉴얼', 'Title')
p('Ubuntu 20.04 Relay와 Windows 10 및 11 원격제어 운영')
p('작성 기준 2026년 11월 6일  |  서버 61.105.141.21  |  TCP 61000')
p('이 문서는 관리자가 GitHub에서 Relay 서버를 설치하고, Windows HOST와 TARGET 및 감시 프로그램을 실행한 뒤 업데이트와 장애 복구를 수행하는 절차를 설명합니다. 서버 인증서 준비와 방화벽 허용을 마친 다음 두 PC에서 연결을 검증하세요.')
h('구성 및 접속 흐름')
table(['구성', '실행 환경', '역할'], [
    ['HOST', 'Windows 10 및 11 x64', '비밀번호 인증 후 대상 목록 조회와 원격제어'],
    ['TARGET', 'Windows 10 및 11 x64', 'Relay 연결 유지와 화면 전송 및 입력 처리'],
    ['Watchdog', 'TARGET와 같은 Windows 사용자', 'TARGET 종료 및 UI 무응답 감지와 재실행'],
    ['Relay', 'Ubuntu 20.04 및 Python 3.8 이상', '두 PC의 TLS 연결 중계']], [2.6, 5.2, 9.2])
p('HOST → 공인 Relay TCP 61000 ← TARGET. 두 PC 모두 서버로 외부 연결을 하므로 TARGET 공유기의 포트 포워딩은 필요하지 않습니다. TARGET이 꺼지거나 인터넷이 끊긴 동안에는 접속할 수 없습니다.')
h('기존 스마트폰 서비스와의 분리')
p('PC용 서비스는 pcremote-relay, 설치 경로는 /opt/pcremote와 /etc/pcremote입니다. 기존 스마트폰 RemoteControl의 TCP 55000 및 remotecontrol-relay 서비스는 변경하지 않습니다. 앱과 서버는 55000부터 60000까지의 예약 포트 사용을 거부합니다.')
h('문서 구성')
p('2쪽 준비 및 인증서 · 3쪽 Ubuntu 설치 · 4쪽 Windows 실행 · 5쪽 TARGET 감시 · 6쪽 관리와 업데이트 · 7쪽 장애 대응 · 8쪽 검증과 지원 범위')

page('서버 준비와 인증서')
h('설치 전 확인')
p('Ubuntu 서버에 SSH로 로그인할 수 있는 관리자 계정과 sudo 권한을 준비합니다. 아래 bash 명령은 Windows PowerShell이 아닌 Ubuntu SSH 터미널에서 실행합니다. 서버 주소는 현재 61.105.141.21이며 Windows 설정 화면에서 이후 변경할 수 있습니다.')
code('''lsb_release -ds
python3 --version
sudo ss -ltnp 'sport = :61000'
sudo systemctl status remotecontrol-relay --no-pager''')
p('61000을 다른 프로그램이 사용 중이면 설치를 진행하지 말고 충돌을 해결하세요. 마지막 명령은 기존 스마트폰 서비스가 설치된 경우의 상태 확인용입니다. 설치 전 상태를 기록해 설치 후와 비교합니다.')
h('TLS 인증서 선택')
p('권장 방법은 관리 중인 도메인을 61.105.141.21에 연결하고 해당 도메인의 유효한 서버 인증서를 준비하는 것입니다. 양쪽 Windows 앱에는 인증서와 일치하는 도메인을 입력합니다. 나중에 서버 IP가 바뀌면 DNS와 필요한 방화벽 설정을 갱신합니다.')
p('IP 61.105.141.21로 직접 연결하려면 인증서의 Subject Alternative Name에 IP Address:61.105.141.21이 있어야 하고 Windows가 발급 체인을 신뢰해야 합니다. 도메인 전용 인증서는 IP 접속에 사용할 수 없습니다. 사설 CA를 사용한다면 양쪽 PC의 신뢰 저장소를 관리자가 별도로 구성해야 합니다. 앱에는 인증서 검증 우회 기능이 없습니다.')
code('''openssl x509 -in /path/to/fullchain.pem -noout -dates
openssl x509 -in /path/to/fullchain.pem -noout -text''')
p('명령의 /path/to 경로는 실제 파일로 바꾸세요. fullchain.pem과 privkey.pem을 준비하며 개인 키를 GitHub에 올리지 않습니다. 설치 프로그램은 인증서와 키의 짝을 검사하지만, 접속 주소 일치·Windows 신뢰·갱신은 운영자가 확인해야 합니다.')
h('운영 조건')
p('Relay 서버의 인바운드 TCP 61000과 두 Windows PC의 아웃바운드 TCP 61000을 허용합니다. HTTPS 웹서버가 아닌 전용 TLS/TCP 서비스이므로 일반 HTTP 프록시에 그대로 연결하지 않습니다.')
p('Ubuntu 20.04는 표준 지원이 종료된 버전입니다. 사용을 유지할 경우 Ubuntu Pro/ESM 등 보안 유지보수 상태를 확인하세요. 공식 안내: https://ubuntu.com/20-04')

page('Ubuntu 서버 설치')
h('GitHub에서 받기')
code('''sudo apt-get update
sudo apt-get install -y git python3 ca-certificates
git clone https://github.com/forlovesea/work.git
cd work/PCRemoteControl''')
p('이미 work 저장소가 있으면 새로 복제하지 않고 해당 저장소에서 git pull --ff-only origin main을 실행한 뒤 PCRemoteControl 폴더로 이동합니다. 로컬 수정 때문에 pull이 거부되면 강제 덮어쓰기하지 말고 수정 내용을 먼저 보관하세요.')
h('전용 서비스 설치')
code('''sudo sh server/install.sh /path/to/fullchain.pem /path/to/privkey.pem''')
p('스크립트는 pcremote 사용자를 만들고 서버 코드·인증서·서비스를 PC용 전용 경로에 설치합니다. 새 설치의 기본 비밀번호는 jjh1234입니다. 재설치 시 기존 비밀번호를 유지합니다. 서비스는 부팅 시 자동 시작되며 비정상 종료 시 systemd가 재시작합니다.')
h('방화벽과 상태 확인')
code('''sudo ufw status
# UFW를 사용 중인 경우에만 규칙 추가
sudo ufw allow 61000/tcp
sudo systemctl is-enabled pcremote-relay
sudo systemctl is-active pcremote-relay
sudo ss -ltnp 'sport = :61000'
sudo journalctl -u pcremote-relay -n 50 --no-pager''')
p('클라우드 보안 그룹이나 서버 앞단 방화벽에도 TCP 61000을 허용합니다. UFW를 새로 켜거나 전체 규칙을 초기화하지 마세요. SSH 및 기존 서비스 접속을 유지해야 합니다. 서비스 active만으로 외부 접속까지 검증된 것은 아닙니다.')
h('설치 경로')
table(['항목', '경로'], [
    ['실행 코드 및 직전 코드', '/opt/pcremote/relay.py 및 relay.py.previous'],
    ['비밀번호 설정', '/etc/pcremote/relay.env'],
    ['인증서 및 개인 키', '/etc/pcremote/fullchain.pem 및 privkey.pem'],
    ['서비스 정의', '/etc/systemd/system/pcremote-relay.service']], [4.6, 12.4])
p('설치 완료 후 기존 remotecontrol-relay 상태와 스마트폰 연결을 확인합니다. 이 문서의 설치 스크립트는 기존 서비스를 중지하거나 재시작하지 않습니다.')

page('Windows 프로그램 설치와 실행')
h('실행 파일 준비')
p('배포 폴더 release/win-x64 전체를 고정된 위치에 복사합니다. PCRemoteControl.exe와 PCRemoteControl.Watchdog.exe는 같은 폴더에 두세요. 자체 포함 x64 배포는 .NET 별도 설치가 필요 없습니다. 실행 파일은 소스 저장소에 포함하지 않으므로 개발 PC에서 아래 명령으로 빌드하거나 제공된 배포 폴더를 복사합니다.')
code(r'''# Windows PowerShell 및 .NET 8 SDK
cd work\PCRemoteControl
.\build.ps1''')
p('스크립트 실행 정책으로 차단되는 환경에서는 조직 정책을 따르거나 build.ps1에 적힌 두 dotnet publish 명령을 각각 실행하세요. 런타임 팩 복원에는 NuGet 네트워크 접근이 필요할 수 있습니다.')
h('TARGET 초기 설정')
p('1. PCRemoteControl.exe --target으로 실행합니다. Relay 주소 61.105.141.21 또는 인증서 도메인, 포트 61000, 비밀번호와 PC 이름을 입력합니다.')
p('2. 서버 연결을 누릅니다. 이 동작은 비밀번호를 아는 HOST의 화면 보기와 키보드·마우스 제어를 허용합니다. 연결 상태와 인증서 오류를 확인합니다.')
p('3. 설정을 마치면 TARGET 창을 정상 종료하고 Start-TARGET.cmd를 실행합니다. 이후에는 감시 프로그램이 TARGET 실행과 자동 접속을 담당합니다.')
h('HOST 실행과 원격제어')
p('1. Start-HOST.cmd를 실행하거나 PCRemoteControl.exe에서 HOST 역할을 선택합니다. TARGET과 동일한 서버 주소·포트·비밀번호를 입력합니다.')
p('2. 서버 연결을 누르면 인증 후 TARGET 목록이 표시됩니다. 목록은 5초마다 갱신됩니다. 연결 가능 대상을 선택하고 원격접속을 누릅니다.')
p('3. 원격 화면을 클릭하면 키보드·마우스 입력을 전달합니다. F11은 전체 화면 전환, 전체 화면에서 Esc는 창 모드 복귀입니다. 원격접속 종료는 해당 제어 세션만 끝내고 서버 연결을 유지합니다.')
p('TARGET의 연결 중지는 제어와 서버 연결을 중지합니다. 대상당 동시에 한 HOST만 제어할 수 있습니다. 같은 PC에서 HOST와 TARGET을 동시에 사용하면 화면이 반복 표시될 수 있으므로 실제 검증에는 서로 다른 PC를 사용하세요.')

page('TARGET 감시 프로그램 운영')
h('자동 복구 방식')
table(['상황', '처리'], [
    ['프로세스 비정상 종료', '5초 후 재실행과 Relay 자동 연결'],
    ['UI 응답 신호 없음', '실행 후 유예 60초 및 신호 지연 60초 초과 시 재시작'],
    ['반복 장애', '재시도 간격 5 10 20 40 60초 후 60초 유지'],
    ['5분 정상 실행', '연속 실패 횟수 초기화'],
    ['TARGET 연결 중지', '감시 복구 일시 중단 · 서버 연결을 누르면 재개'],
    ['TARGET 정상 종료', '자동 재실행 중단 · 감시 시작으로 재개']], [5, 12])
p('Watchdog는 2초마다 자신이 실행한 TARGET 프로세스와 UI 응답 파일을 확인합니다. 네트워크 단절은 TARGET 내부 재연결 기능이 담당하며, 네트워크 오류만으로 프로세스를 강제 종료하지 않습니다.')
h('버튼과 종료 의미')
p('감시 창의 감시 중지나 창 닫기는 감시만 중지하며 TARGET은 계속 실행됩니다. 접속을 차단하려면 TARGET에서 연결 중지를 누르세요. 수동 실행 중인 TARGET은 감시 프로그램이 인계받거나 종료하지 않습니다. 기존 TARGET을 닫고 감시 시작을 누릅니다.')
h('로그인 후 자동 실행')
p('기본 배포는 자동 시작을 등록하지 않습니다. 필요하면 배포 폴더를 고정한 뒤 Win+R에서 shell:startup을 열고 PCRemoteControl.Watchdog.exe의 바로가기를 넣습니다. 다음 Windows 로그인 후 실행 여부를 확인합니다. 자동 실행 해제는 해당 바로가기를 삭제하면 됩니다.')
p('로그인 전 Windows 서비스로 동작하지 않습니다. 로그아웃, PC 전원 꺼짐, 절전 또는 Watchdog 자체 종료는 복구 대상이 아닙니다. Windows 전원 설정과 자동 로그인 여부는 운영 정책에 따라 별도로 관리하세요.')
h('저장 정보와 로그')
p('설정과 로그는 %LOCALAPPDATA%\\PCRemoteControl에 있습니다. settings.json에 서버 주소·포트·PC 이름·기기 ID를 저장합니다. target-password.bin은 TARGET 비밀번호를 현재 Windows 사용자 DPAPI로 암호화한 파일이며 다른 사용자 계정으로 복사해 사용할 수 없습니다. HOST 비밀번호는 저장하지 않습니다.')
p('watchdog.log에는 실행·종료·재시도·오류를 기록하고 약 512KB에서 .old로 순환합니다. 비밀번호는 로그나 실행 명령줄에 넣지 않습니다. 문제가 생기면 해당 로그와 발생 시각을 함께 확인합니다.')

page('서버 관리와 업데이트')
h('일상 관리')
code('''sudo systemctl status pcremote-relay --no-pager
sudo journalctl -u pcremote-relay -f
sudo systemctl restart pcremote-relay
sudo systemctl stop pcremote-relay
sudo systemctl start pcremote-relay''')
p('restart는 PC 원격 세션을 끊습니다. 서버가 복구되면 TARGET은 5초 간격으로 재접속하고 HOST는 다시 서버 연결을 누릅니다. 서비스 중지 상태는 다음 start 또는 재부팅 시 바뀔 수 있습니다. 부팅 자동 시작까지 끄려면 sudo systemctl disable --now pcremote-relay를 사용합니다.')
h('업데이트와 코드 롤백')
code(r'''cd ~/work
git pull --ff-only origin main
cd PCRemoteControl
sudo sh server/install.sh \
  /etc/pcremote/fullchain.pem /etc/pcremote/privkey.pem''')
p('저장소 위치가 다르면 cd 경로를 바꾸세요. 업데이트 전에 설정·인증서·서비스 파일을 안전한 관리자 보관 위치에 백업합니다. 설치 스크립트는 직전 relay.py만 한 세대 보관하며 설정 전체의 백업 기능은 아닙니다.')
code('''sudo cp /opt/pcremote/relay.py.previous /opt/pcremote/relay.py
sudo systemctl restart pcremote-relay''')
p('롤백 명령은 .previous가 있는 경우에만 사용합니다. 설정과 인증서 또는 서비스 정의까지 바뀐 경우에는 별도 백업에서 필요한 파일도 복구해야 합니다.')
h('비밀번호 및 인증서 변경')
code('''sudoedit /etc/pcremote/relay.env
# PCREMOTE_PASSWORD 값을 변경한 뒤 저장
sudo systemctl restart pcremote-relay''')
p('양쪽 Windows 앱에도 새 비밀번호를 입력합니다. TARGET은 연결 중지 후 값을 수정하고 서버 연결을 누르면 암호화 저장 파일이 갱신됩니다. 기본 jjh1234를 아는 사용자는 등록 TARGET을 제어할 수 있으므로 공인 운영 시 변경하세요.')
p('인증서는 원본 위치에서 갱신한 후 install.sh에 새 인증서와 키 경로를 넘겨 PC용 복사본도 갱신합니다. 복사 방식이므로 원본만 갱신하면 적용되지 않습니다. 개인 키는 root:pcremote 소유 및 640 권한을 유지합니다.')

page('장애 진단과 복구')
h('연결 또는 목록이 보이지 않을 때')
p('먼저 서버 서비스와 TCP 61000 수신을 확인하고 Windows에서 아래 명령을 실행합니다. TcpTestSucceeded는 TCP 도달 여부만 의미하며 비밀번호나 TLS 검증 성공을 보장하지 않습니다.')
code('''Test-NetConnection 61.105.141.21 -Port 61000''')
table(['증상', '확인 및 조치'], [
    ['TLS 인증서 오류', '앱 주소와 SAN 일치, 인증서 만료, Windows 신뢰 체인 및 PC 시간을 확인'],
    ['Authentication failed', '서버 relay.env와 양쪽 앱 비밀번호 일치 여부 확인'],
    ['Too many attempts', '잘못된 비밀번호를 수정한 뒤 마지막 실패부터 60초 이상 대기'],
    ['대상 목록이 비어 있음', 'TARGET 앱 실행 및 서버 연결 상태, 동일 서버 사용 여부 확인'],
    ['Target ID already online', '중복 TARGET과 복제된 settings.json 확인 · 이전 연결 정리까지 대기'],
    ['Target unavailable or busy', '기존 HOST 접속을 끝내고 목록을 새로고침'],
    ['화면은 보이나 입력 안 됨', '원격 화면 클릭 및 TARGET 관리자 권한 창 여부 확인'],
    ['Watchdog가 재실행 안 함', '감시 창 실행 여부, 정상 종료나 연결 중지 상태, 로그 확인']], [5, 12])
h('입력과 화면의 제한')
p('잠금·로그인 화면, UAC 보안 데스크톱, Ctrl+Alt+Del은 지원하지 않습니다. 일반 권한 TARGET은 관리자 앱에 입력을 보낼 수 없습니다. 잠금 상태에서 접속이 필요한 운영 방식이라면 별도 설계가 필요하며 이 프로그램으로 보안 화면을 우회할 수 없습니다.')
h('서버 주소나 포트 변경')
p('서버 주소는 양쪽 앱에서 연결 중지 후 수정하고 서버 연결을 누릅니다. 새 주소에 맞는 TLS 인증서도 준비합니다. 포트 변경 시 서비스 ExecStart의 --port, 방화벽·보안 그룹, 양쪽 앱 포트를 함께 변경하세요. 이 버전 install.sh는 61000 고정 서비스 파일을 재설치하므로 사용자 지정 포트를 적용했다면 업데이트 뒤 다시 확인해야 합니다.')

page('검증 절차와 지원 범위')
h('자동 검사')
code('''# Ubuntu 또는 Python이 있는 개발 환경
cd PCRemoteControl/server
python3 -m unittest -v test_relay
# Windows 및 .NET 8 SDK
dotnet run --project PCRemoteControl/RecoveryTests/RecoveryTests.csproj -c Release''')
p('Relay 테스트는 인증·중복 ID·목록·세션 연결·사용 중 거부·프레임 및 입력 전달·정리·크기 제한을 검사합니다. 루프백 테스트는 평문이며 운영 서버는 TLS만 허용합니다. 복구 검사는 재시도 정책·UI 시간 제한·DPAPI 암호화 복원을 검사합니다.')
h('운영 인수 확인')
p('1. Ubuntu 재부팅 후 pcremote-relay 자동 시작과 61000 수신을 확인합니다. 기존 스마트폰 서비스와 다른 서버 서비스도 정상인지 확인합니다.')
p('2. 서로 다른 NAT 환경의 Windows 10 및 11에서 TARGET 목록, 화면, 마우스·키보드·휠, F11과 Esc를 확인합니다.')
p('3. TARGET 연결 중 작업 관리자로 PCRemoteControl.exe만 강제 종료하고 Watchdog 재실행과 Relay 복구를 확인합니다. HOST는 다시 연결합니다.')
p('4. TARGET 정상 종료와 연결 중지에서는 자동 재실행되지 않는지 확인합니다. 감시 시작 또는 서버 연결로 운영을 재개합니다.')
p('5. 네트워크 단절·복구, 잘못된 비밀번호와 인증서 거부, TARGET 중지 후 입력 해제를 확인합니다. 로그와 점검 시각을 보관합니다.')
h('기능 범위')
p('주 모니터 화면을 최대 가로 1600픽셀 JPEG와 약 8fps로 전송합니다. 다중 모니터 선택·오디오·파일 전송·클립보드는 포함하지 않습니다. 한글 입력은 TARGET 입력기 상태에 따르며 Windows 예약 키 조합은 완전 전달하지 않습니다.')
p('TLS는 HOST와 Relay, TARGET과 Relay 사이를 보호합니다. Relay가 화면과 입력을 복호화하므로 신뢰하는 관리자가 운영해야 합니다. 사용자별 계정·대상별 권한 분리는 없으며 공통 비밀번호로 접속합니다.')
h('참고 자료')
p('소스: https://github.com/forlovesea/work/tree/main/PCRemoteControl\nUbuntu 20.04 지원: https://ubuntu.com/20-04\nWindows 입력 제약: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput')
d.core_properties.title = 'PCRemoteControl 설치 실행 관리 매뉴얼'
d.core_properties.subject = 'Ubuntu 20.04 Relay와 Windows HOST TARGET 감시 프로그램 운영'
d.save(ROOT / 'PCRemoteControl_설치_실행_관리_매뉴얼.docx')
print(ROOT / 'PCRemoteControl_설치_실행_관리_매뉴얼.docx')
