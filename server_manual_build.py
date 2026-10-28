from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parent
d=Document(); sec=d.sections[0]
sec.page_height=Cm(29.7); sec.page_width=Cm(21)
sec.top_margin=sec.bottom_margin=Cm(1.8)
sec.left_margin=sec.right_margin=Cm(2)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2']:
 s=d.styles[name]; s.font.name='맑은 고딕'; s.font.color.rgb=RGBColor(0,0,0)
 s.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'맑은 고딕')
d.styles['Normal'].font.size=Pt(10)
d.styles['Normal'].paragraph_format.space_after=Pt(6)
d.styles['Normal'].paragraph_format.line_spacing=1.15
d.styles['Heading 1'].font.size=Pt(19)
d.styles['Heading 2'].font.size=Pt(12)
foot=sec.footer.paragraphs[0]; foot.alignment=2
foot.add_run('서버 운영 매뉴얼  |  ')
field=OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); foot._p.append(field)
def p(t): d.add_paragraph(t)
def h(t): d.add_heading(t,2)
def code(t):
 t=t.replace('\x08',r'\b')
 for line in t.strip().splitlines():
  z=d.add_paragraph(); z.paragraph_format.space_after=Pt(0); z.paragraph_format.line_spacing=1.0
  r=z.add_run(line); r.font.name='Consolas'; r.font.size=Pt(8)
 d.add_paragraph().paragraph_format.space_after=Pt(0)
def page(title):
 d.add_page_break(); d.add_heading(title,1)
def table(headers,rows,widths):
 t=d.add_table(rows=1, cols=len(headers)); t.autofit=False
 for c,w in zip(t.columns,widths): c.width=Cm(w)
 for i,v in enumerate(headers): t.rows[0].cells[i].text=v
 for row in rows:
  for c,v in zip(t.add_row().cells,row): c.text=v
 for j,row in enumerate(t.rows):
  for c,w in zip(row.cells,widths):
   c.width=Cm(w); pr=c._tc.get_or_add_tcPr()
   borders=OxmlElement('w:tcBorders')
   for side in ['top','left','bottom','right']:
    e=OxmlElement('w:'+side); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:color'),'D9D9D9'); borders.append(e)
   pr.append(borders)
   if j==0:
    sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),'E8EEF3'); pr.append(sh)
   for par in c.paragraphs:
    for r in par.runs: r.font.size=Pt(9); r.bold=j==0
  trPr=row._tr.get_or_add_trPr(); trPr.append(OxmlElement('w:cantSplit'))
 t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
 p('')

d.add_heading('Ubuntu 프로젝트 서버 운영 매뉴얼',0)
p('부팅 자동 시작과 재시작 및 장애 확인')
p('대상 서버 61.105.141.21  |  Ubuntu 20.04  |  작성일 2026년 10월 27일')
p('이 매뉴얼은 화상회의 Moa, 현장 설치 버전관리, BatteryWatch 서버의 부팅 후 점검과 복구 절차를 설명합니다. 원격제어 중계서버는 부록에서 다룹니다. Windows의 work 폴더는 개발 작업 위치이며, 이 문서의 bash 명령은 Ubuntu 서버의 SSH 터미널에서 실행합니다.')
p('기본 원칙은 마운트와 IP 확인 → 서비스 확인 → 수신 포트 확인 → HTTPS 응답 확인 → 실제 앱 동작 확인입니다. active 상태만으로 외부 접속이나 데이터 저장의 정상 동작까지 확인된 것은 아닙니다.')
h('목차')
titles=['1 서버 구성과 확인된 상태','2 재부팅 직후 빠른 점검','3 부팅 시 프로그램 자동 시작','4 디스크 마운트와 시작 순서','5 화상회의 서버 운영','6 BatteryWatch 서버 운영','7 현장 설치 버전관리 운영','8 프로세스와 로그 확인','9 장애별 복구와 재부팅 검증','10 원격제어와 백업 및 참고 자료']
for i,t in enumerate(titles):
 z=d.add_paragraph()
 link=OxmlElement('w:hyperlink'); link.set(qn('w:anchor'),f'chapter{i+1}')
 r=OxmlElement('w:r'); text=OxmlElement('w:t'); text.text=t; r.append(text); link.append(r); z._p.append(link)
p('목차 항목은 해당 장으로 이동하는 내부 링크입니다. Word의 탐색 창에서도 제목별로 이동할 수 있습니다.')

page(titles[0])
table(['서비스','실행 단위와 경로','접속 및 포트'],[
 ['화상회의','moa.service 및 nginx.service\n/opt/moa/current\n/var/lib/moa','HTTPS 10443\n내부 127.0.0.1:8000'],
 ['설치 버전관리','apache2.service\nInstalledManagementVersion/public\ndata/installed-management.sqlite','HTTPS 443\n/installed-management/'],
 ['BatteryWatch','batterywatch.service\nBatteryWatch/server\nserver.local.json','HTTPS TCP 8443'],
 ['원격제어','remotecontrol-relay.service\n/opt/remotecontrol','TLS TCP 55000\n실제 서비스 등록 확인 필요']],[3,9,5])
p('Ubuntu 프로젝트 기준 경로는 /home/jihyun/proj/github/work 입니다. BatteryWatch의 실제 Python 실행 경로와 설정 파일은 설치된 systemd 유닛에서 확인합니다. 서비스 예제 파일의 YOUR_USER 또는 /ABSOLUTE/PATH 값을 운영 서버에 그대로 덮어쓰지 않습니다.')
h('2026년 10월 27일 진단 결과')
p('루트 디스크는 117GB 중 70GB 사용, 여유 42GB였습니다. /dev/sdb1은 916GB 중 26GB 사용, 여유 845GB였습니다. inode도 충분하며 /home/jihyun은 /data/home/jihyun의 bind 마운트로 연결되어 있습니다. 프로젝트 폴더가 원래 경로에 존재합니다.')
p('Moa는 실행 중이었고 Nginx는 61.105.141.21:10443 주소 바인딩 실패로 중지되었습니다. BatteryWatch는 의존성 실패로 시작되지 않았습니다. Apache는 실행 중이며 443과 9230 포트를 수신했습니다. 이후 복구 명령의 성공 여부는 실제 실행 결과로 기록해야 합니다.')
p('BatteryLogReport는 Windows 및 Android에서 실행하는 보고서 생성 프로그램입니다. Ubuntu 서버의 자동 시작 서비스 대상에 포함하지 않습니다.')

page(titles[1])
p('재부팅 후 SSH로 접속한 다음 순서대로 실행합니다. 아래 명령은 조회용이며 서버 설정을 바꾸지 않습니다.')
h('디스크와 IP 확인')
code('''date
uptime
df -hT / /home/jihyun /data
df -i / /home/jihyun
findmnt -T /home/jihyun
ip -4 -br address''')
h('서비스와 수신 포트 확인')
code('''sudo systemctl --failed --no-pager
sudo systemctl status batterywatch moa nginx apache2 --no-pager -l
sudo ss -lntp | grep -E ':(443|8443|10443|8000|55000)\b' ''')
p('정상 기준: 필요한 서비스가 active (running)이고 각 TCP 포트가 기대한 프로세스에 연결되어 있어야 합니다. Moa의 8000은 127.0.0.1 전용 수신이 정상입니다. UDP 8443의 OpenVPN은 TCP 8443의 BatteryWatch와 별개입니다.')
h('웹 응답과 외부 접속 확인')
code('''curl --noproxy '*' --connect-timeout 5 --max-time 15 \\
  -sS -o /dev/null -w 'HTTP=%{http_code}\\n' \\
  https://61.105.141.21:10443/
curl --noproxy '*' --connect-timeout 5 --max-time 15 \\
  -sS -o /dev/null -w 'HTTP=%{http_code}\\n' \\
  https://61.105.141.21/installed-management/''')
p('200 또는 로그인 화면으로의 302 응답은 웹 경로가 응답한다는 뜻입니다. 인증서 오류는 별도로 해결합니다. 서버 내부 접속 성공 후 외부 PC와 LTE 스마트폰에서 접속하고, 회의 입장·설치 정보 조회·BatteryWatch 조회까지 확인합니다.')

page(titles[2])
p('이미 설치된 서비스를 자동 시작 대상으로 등록하는 절차입니다. 서비스가 없으면 먼저 실제 배포 문서와 유닛 파일을 확인합니다. 등록 명령은 재설치나 설정 초기화가 아닙니다.')
table(['명령','효과'],[['enable','다음 부팅 자동 시작 등록. 지금 시작하지 않음'],['start','현재 시작. 자동 시작 등록은 바꾸지 않음'],['enable --now','자동 시작 등록과 즉시 시작'],['restart','중지 후 다시 시작. 연결이 끊길 수 있음'],['reload','지원되는 서비스의 설정 재적용'],['daemon-reload','systemd 유닛 수정 내용을 읽음. 앱 재시작 아님'],['disable','다음 부팅 자동 시작 해제. 현재 실행은 유지']],[4,13])
code('''systemctl is-enabled batterywatch moa nginx apache2
sudo systemctl enable batterywatch moa nginx apache2
systemctl is-enabled batterywatch moa nginx apache2''')
p('각 항목이 enabled인지 확인합니다. failed 상태는 enable만으로 복구되지 않습니다. 아래처럼 서비스별 검사를 통과한 후 시작합니다.')
code('''sudo systemctl start batterywatch
sudo systemctl start moa
sudo nginx -t && sudo systemctl start nginx
sudo apache2ctl configtest && sudo systemctl start apache2''')
h('설정 변경 후 적용')
code('''sudo systemctl daemon-reload
sudo systemctl restart batterywatch
sudo systemctl status batterywatch --no-pager -l''')
p('위 예시는 BatteryWatch 유닛을 변경한 경우입니다. 변경하지 않은 정상 서비스까지 일괄 재시작하지 않습니다. 서비스 실행은 systemd로 관리하고, 같은 DB와 포트로 수동 Python 서버를 동시에 띄우지 않습니다.')

page(titles[3])
h('현재 마운트 구조')
code('''/dev/sdb1  ->  /data
/data/home/jihyun  ->  /home/jihyun  (bind)''')
p('fstab의 기존 UUID와 옵션을 보존합니다. 아래는 제공된 진단에서 확인된 구조이며, 복사하여 중복 추가하는 명령이 아닙니다.')
code('''장치 UUID: 5ff438d5-afd9-4aec-bafb-08e20d302ae1
마운트 위치: /data    파일시스템: ext4
옵션: defaults,nofail,x-systemd.device-timeout=10s
bind 원본: /data/home/jihyun    대상: /home/jihyun
옵션: bind,x-systemd.requires-mounts-for=/data/home/jihyun''')
p('위 내용은 fstab 행을 항목별로 풀어 쓴 설명이며 그대로 붙여 넣는 설정이 아닙니다. x-systemd.requires-mounts-for는 마운트 의존성이고, 실제 경로 연결은 bind 옵션이 수행합니다.')
code('''sudo findmnt --verify --verbose
sudo systemctl status data.mount home-jihyun.mount --no-pager -l
sudo journalctl -b -u data.mount -u home-jihyun.mount --no-pager''')
h('홈 경로가 필요한 서비스의 마운트 의존성')
p('부팅 시 마운트 순서 문제가 확인되면 기존 drop-in을 확인하고 다음 항목을 추가하거나 병합합니다. 기존 Requires 항목을 근거 없이 삭제하지 않습니다.')
code('''sudo systemctl edit batterywatch.service

[Unit]
RequiresMountsFor=/home/jihyun/proj/github/work/BatteryWatch/server''')
p('위 [Unit] 두 줄은 편집기에 넣는 내용이며 셸에서 실행하는 명령이 아닙니다. Apache도 홈 경로를 직접 사용하므로 필요하면 같은 방식으로 설정합니다.')
code('''sudo systemctl edit apache2.service

[Unit]
RequiresMountsFor=/home/jihyun/proj/github/work/InstalledManagementVersion''')
code('''sudo systemctl daemon-reload
sudo systemctl show batterywatch apache2 -p RequiresMountsFor''')
p('마운트가 활성화되어도 파일·ACL 누락은 별도 문제입니다. 현재 구조가 정상이라면 umount, 디스크 포맷, 전체 chmod 또는 chown을 하지 않습니다.')

page(titles[4])
p('Moa가 회의 기능을 제공하고 Nginx가 HTTPS 10443 요청을 내부 127.0.0.1:8000으로 전달합니다. Nginx만 실패하면 Moa를 재시작할 필요가 없습니다.')
h('조회와 재시작')
code('''sudo systemctl status moa nginx --no-pager -l
sudo journalctl -u moa -u nginx -b -n 80 --no-pager
sudo nginx -t && sudo systemctl restart nginx
# Moa 자체 오류나 설정 변경이 있을 때만 실행
sudo systemctl restart moa''')
p('Moa 재시작은 진행 중인 회의와 기록 처리에 영향을 줄 수 있습니다. 회의 종료와 기록 저장 상태를 확인한 뒤 실행합니다. /opt/moa/current, /etc/moa/moa.env, /var/lib/moa를 보존합니다.')
h('IP 바인딩 오류 복구')
p('Cannot assign requested address는 시작 당시 지정 IP가 없다는 의미입니다. 실제 로그에서는 부팅 시 61.105.141.21:10443 바인딩이 실패했습니다. 이후 IP가 준비되었는지 먼저 확인하고 Nginx를 다시 시작합니다.')
code('''ip -4 -br address
sudo nginx -t && sudo systemctl restart nginx
sudo ss -lntp | grep ':10443' ''')
h('부팅 시 IP 준비 순서 보완')
code('''systemctl is-active NetworkManager systemd-networkd
systemctl is-enabled NetworkManager-wait-online.service \\
  systemd-networkd-wait-online.service
sudo systemctl show nginx -p Wants -p After''')
p('실제 사용 중인 네트워크 관리자에 맞는 wait-online 서비스와 공인 IP 설정 시점을 확인합니다. 둘 다 무조건 활성화하지 않습니다. IP를 별도 스크립트가 추가한다면 그 스크립트의 유닛과 순서도 확인해야 합니다.')
code('''sudo systemctl edit nginx.service

[Unit]
Wants=network-online.target
After=network-online.target''')
p('편집 후 daemon-reload를 실행합니다. network-online만으로 특정 IP가 보장되는 것은 아닙니다. 정상 복구 후 계획된 재부팅으로 다시 확인합니다. 주소 문제를 피하려고 수신 범위를 0.0.0.0으로 일괄 변경하지 않습니다.')

page(titles[5])
h('실제 Python과 설정 경로 확인')
code('''sudo systemctl show batterywatch \\
  -p User -p WorkingDirectory -p ExecStart -p FragmentPath
sudo systemctl status batterywatch --no-pager -l
sudo journalctl -u batterywatch -b -n 80 --no-pager''')
p('서버 설정은 일반적으로 BatteryWatch/server/server.local.json이며 DB와 인증서 경로는 설정 파일 기준으로 해석됩니다. 실제 유닛의 --config 경로를 우선합니다. 토큰이 들어 있는 설정 전체를 공개하지 않습니다.')
h('시작과 정지 및 재시작')
code('''sudo systemctl start batterywatch
sudo systemctl stop batterywatch
sudo systemctl restart batterywatch''')
p('위 명령은 목적에 맞게 하나씩 선택합니다. 단순 상태 확인에는 status를 사용합니다. 정지 후 서비스를 계속 사용하려면 start로 복귀해야 합니다.')
h('의존성 실패 확인')
code('''sudo systemctl show batterywatch \\
  -p Requires -p Requisite -p BindsTo -p After -p RequiresMountsFor
sudo systemctl list-dependencies batterywatch --all
sudo systemctl status data.mount home-jihyun.mount --no-pager -l
sudo journalctl -b --no-pager | \\
  grep -Ei 'batterywatch|home-jihyun|data\\.mount|dependency failed|timed out waiting' ''')
p('Dependency failed는 Python 코드가 실행되기 전 의존 대상이 실패했을 수 있음을 뜻합니다. 어떤 대상인지 확인한 후 해당 마운트 또는 서비스를 복구합니다. reset-failed는 실패 표시와 시작 제한을 초기화할 뿐 원인을 고치지 않습니다.')
code('''# 원인을 수정한 뒤 실행
sudo systemctl reset-failed batterywatch
sudo systemctl start batterywatch
sudo ss -lntp | grep ':8443' ''')
p('정상 기준은 서비스 실행, TCP 8443 수신, 앱의 인증된 조회 성공입니다. Ubuntu 기본 python3가 아닌 기존 Python 3.12 또는 기존 가상환경 경로를 유지합니다. systemd 실행 중 server.py run으로 중복 실행하지 않습니다.')

page(titles[6])
p('현장 설치 버전관리는 Apache가 PHP 웹 파일을 서비스합니다. 별도 프로젝트 Python 프로세스가 없어도 정상이며 Apache의 443 포트와 해당 URL을 확인합니다. OpenProject 등 같은 Apache를 쓰는 서비스에 대한 영향을 고려합니다.')
code('''sudo systemctl status apache2 --no-pager -l
sudo apache2ctl configtest
sudo apache2ctl -S
sudo ss -lntp | grep ':443'
sudo tail -n 60 /var/log/apache2/error.log''')
p('가상호스트별 ErrorLog를 따로 지정한 경우 해당 로그도 확인합니다. 설정 검사 성공 후 설정만 적용하려면 reload, 프로세스 재시작이 필요하면 restart를 선택합니다.')
code('''sudo apache2ctl configtest && sudo systemctl reload apache2
# 재시작이 필요한 경우에만 선택
sudo apache2ctl configtest && sudo systemctl restart apache2''')
h('접근 권한과 데이터 쓰기 확인')
code('''APP=/home/jihyun/proj/github/work/InstalledManagementVersion
namei -l "$APP/public/index.php"
sudo getfacl /home/jihyun "$APP/data"
sudo -u www-data test -r "$APP/public/index.php" && echo READ_OK
sudo -u www-data test -w "$APP/data" && echo WRITE_OK''')
p('Permission denied 또는 403이 확인된 경우에만 필요한 ACL을 복구합니다. 다음은 기존 배포 지침의 상위 경로 통과 권한과 데이터 폴더 권한 예시입니다.')
code('''for path in /home/jihyun /home/jihyun/proj \\
  /home/jihyun/proj/github /home/jihyun/proj/github/work; do
  sudo setfacl -m u:www-data:--x "$path"
done
sudo setfacl -m u:www-data:rx "$APP"
sudo setfacl -m u:www-data:rwx "$APP/data"
sudo setfacl -m d:u:www-data:rwx "$APP/data"''')
p('기존 DB 파일의 ACL은 default ACL만으로 바뀌지 않습니다. public 파일 읽기와 기존 SQLite 파일 쓰기 권한도 별도 확인합니다. data/installed-management.sqlite 및 data/password.hash를 초기화하거나 삭제하지 않습니다.')

page(titles[7])
h('서비스 단위 확인')
code('''sudo systemctl status batterywatch moa nginx apache2 --no-pager -l
systemctl is-active batterywatch moa nginx apache2
sudo systemctl show batterywatch -p MainPID -p SubState -p Result
sudo systemctl list-units --type=service --all''')
p('active (running)은 실행 중, inactive (dead)는 중지, failed는 실패 상태입니다. enabled는 부팅 등록 여부이므로 실행 중이라는 뜻이 아닙니다.')
h('실행 프로세스와 포트의 연결')
code('''ps -eo pid,ppid,user,etime,%cpu,%mem,args --sort=-%cpu | head -n 25
pgrep -af 'server.py|nginx|apache2|relay.py'
sudo ss -lntp
sudo ss -lnup''')
p('PID는 매번 달라집니다. 과거 로그의 PID를 그대로 종료하지 않습니다. 여러 Python 서버가 있으므로 pkill python 또는 killall python으로 일괄 종료하지 않습니다. systemd 서비스는 systemctl stop 또는 restart를 사용합니다.')
h('로그 조회')
code('''# 이번 부팅 로그
sudo journalctl -b -u batterywatch -n 100 --no-pager
# 실시간 추적 종료는 Ctrl+C이며 서버는 계속 실행됨
sudo journalctl -u batterywatch -f
# 이전 부팅 로그 목록과 조회
journalctl --list-boots
sudo journalctl -b -1 -u nginx --no-pager
# 오류 수준만 조회
sudo journalctl -b -p err --no-pager''')
p('이전 부팅 로그는 journal 보존 설정에 따라 없을 수 있습니다. 오류 전후의 시간, 서비스 이름, 실패 메시지를 함께 기록합니다. 로그 공유 전 토큰·암호·개인키 등 민감 정보를 가립니다.')

page(titles[8])
table(['오류 또는 증상','확인과 조치'],[
 ['Dependency failed','Requires와 마운트 유닛 확인 → 실패한 의존 대상 복구 → start'],
 ['Cannot assign requested address','ip address로 해당 IP 확인 → IP 준비 후 Nginx 검사 및 시작'],
 ['Address already in use','ss -lntp로 동일 TCP 주소와 포트 소유자 확인. 무조건 종료 금지'],
 ['200/CHDIR 또는 No such file','WorkingDirectory와 bind 마운트, 경로 및 링크 확인'],
 ['203/EXEC','ExecStart의 Python 존재, 링크, 실행 권한과 noexec 옵션 확인'],
 ['Permission denied 또는 403','서비스 계정의 상위 경로 통과 및 파일 접근 권한 확인'],
 ['readonly database 또는 500','DB 파일과 폴더 쓰기 권한, PHP 및 앱 로그 확인'],
 ['인증서 오류','만료일, IP SAN, 체인과 앱 신뢰 설정 확인. 검증 우회 금지'],
 ['서버 내부 성공 외부 실패','외부 접속 주소, 방화벽, 라우팅 및 NAT를 순서대로 확인']],[6,11])
h('계획된 재부팅 검증')
p('서비스 복구 후 유지보수 시간을 정합니다. 회의 종료, DB와 설정 백업, SSH 재접속 경로를 확인한 뒤 재부팅합니다. 단순 장애 조사 중에는 먼저 원인을 확인합니다.')
code('''systemctl is-enabled batterywatch moa nginx apache2
sudo findmnt --verify --verbose
sudo nginx -t
sudo apache2ctl configtest
# 위 검사 성공 및 유지보수 준비 후 실행
sudo reboot''')
p('재접속 후 2장의 점검을 반복합니다. 자동 시작 등록 여부, 마운트, 공인 IP, 서비스, TCP 포트, 외부 HTTPS 접속, 실제 앱 조회 순으로 확인합니다. 재부팅 전 성공과 재부팅 후 성공을 별도로 기록합니다.')
p('운영 기록 항목: 점검 일시 / 변경한 파일과 항목 / 재시작 서비스 / 오류 원문 / 조치 내용 / 외부 PC 확인 / 스마트폰 확인 / 데이터 저장 확인 / 다음 조치.')

page(titles[9])
h('원격제어 중계서버')
p('프로젝트 기본 유닛명은 remotecontrol-relay.service입니다. 제공된 포트 목록에서 TCP 55000의 Python 프로세스는 확인되었으나 유닛 등록 상태는 별도 확인해야 합니다.')
code('''sudo systemctl status remotecontrol-relay --no-pager -l
sudo systemctl show remotecontrol-relay -p ExecStart -p User
systemctl is-enabled remotecontrol-relay
# 설치된 유닛과 설정을 확인한 뒤 자동 시작 등록
sudo systemctl enable remotecontrol-relay
# 필요 시 실행하며 진행 중 연결은 끊길 수 있음
sudo systemctl restart remotecontrol-relay
sudo ss -lntp | grep ':55000' ''')
h('백업과 보존 대상')
p('BatteryWatch: 실제 설정 JSON, 설정이 가리키는 DB·로그·인증서와 서비스 유닛. 설치 버전관리: data 디렉터리의 SQLite DB와 암호 해시. Moa: /etc/moa, /var/lib/moa, 현재 릴리스 링크와 Python 환경. 원격제어: /etc/remotecontrol의 인증서·키와 서비스 설정을 보존합니다.')
p('DB가 실행 중이면 단순 파일 복사로 일관성이 보장되지 않을 수 있습니다. 해당 DB의 백업 기능을 사용하거나 서비스를 정지한 뒤 관련 파일을 함께 백업합니다. 같은 /dev/sdb1의 다른 폴더에만 둔 복사본은 디스크 고장에 대한 별도 백업이 아닙니다. 인증서 개인키와 접속 토큰은 GitHub에 올리지 않습니다.')
h('프로젝트 문서')
p('작업 폴더 기준: BatteryWatch/server/SYSTEMD.md 및 README.md, InstalledManagementVersion/README.md, WebConference/RelayServer/deploy/native/moa.service 및 설치 문서, RemoteControl/server/README.md.')
h('공식 참고 자료')
p('systemd 네트워크 준비 순서\nhttps://systemd.io/NETWORK_ONLINE/')
p('systemd 마운트 의존성\nhttps://www.freedesktop.org/software/systemd/man/248/systemd.mount.html')
p('Nginx 설정 검사 명령\nhttps://nginx.org/en/docs/switches.html')
p('문서 기준: 2026년 10월 27일 제공된 서버 진단과 프로젝트 배포 설정. 실제 유닛·포트·인증서 경로가 변경되면 이 매뉴얼도 함께 갱신합니다.')

for i,par in enumerate([p for p in d.paragraphs if p.style.name=='Heading 1'],1):
 start=OxmlElement('w:bookmarkStart'); start.set(qn('w:id'),str(i)); start.set(qn('w:name'),f'chapter{i}')
 end=OxmlElement('w:bookmarkEnd'); end.set(qn('w:id'),str(i)); par._p.insert(0,start); par._p.append(end)
d.core_properties.title='Ubuntu 프로젝트 서버 운영 매뉴얼'
d.core_properties.subject='자동 시작 재시작 프로세스 확인 및 장애 복구'
out=ROOT/'Ubuntu_프로젝트_서버_운영_매뉴얼.docx'; d.save(out)
print(out)
print('paragraphs',len(d.paragraphs),'tables',len(d.tables))
from zipfile import ZipFile
from lxml import etree
with ZipFile(out) as z:
 assert z.testzip() is None
 x=etree.fromstring(z.read('word/document.xml'))
 n={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
 anchors=x.xpath('//w:hyperlink/@w:anchor',namespaces=n)
 bookmarks=x.xpath('//w:bookmarkStart/@w:name',namespaces=n)
 assert len(anchors)==10 and set(anchors)<=set(bookmarks)
 print('PASS ZIP integrity, XML and 10 chapter navigation links')
