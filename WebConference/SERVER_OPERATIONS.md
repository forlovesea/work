# 모아 서버 사용과 운영 안내

2026년 10월 19일 업데이트 · 기능 기준 2392a2d. Ubuntu 20.04의 기존 Moa 서버를 점검·업데이트하고 복구하는 안내입니다. 신규 설치는 [설치 안내](UBUNTU_DEPLOY.md)와 [통합 매뉴얼 10장](화상회의_상세매뉴얼.html#section-10)을 사용하세요.

## 운영 위치

| 항목 | 경로 또는 주소 |
| --- | --- |
| 외부 접속 | https://61.105.141.21:10443 |
| 내부 HTTP | http://127.0.0.1:8000 |
| 코드 다운로드 | 관리자가 clone한 work/WebConference/RelayServer |
| 실행 릴리스 | /opt/moa/current → /opt/moa/releases/release-* |
| Python | /opt/moa/python/3.12.15/bin/python3.12 |
| 환경 설정 | /etc/moa/moa.env |
| Master 키 해시 | /etc/moa/master-key.json |
| 회의록 DB | /var/lib/moa/meetings.db |

같은 서버의 축전지 모니터링·원격제어 서비스는 유지합니다. Moa 재시작은 해당 회의를 종료하며 CPU·네트워크는 다른 서비스와 공유합니다. Nginx·인증서·방화벽·기존 서비스 전체를 재설정하는 방식으로 업데이트하지 않습니다.

## 1 상태 확인과 로그

```bash
sudo systemctl status moa --no-pager -l
sudo systemctl is-enabled moa
readlink -f /opt/moa/current
curl --noproxy '*' -fsS http://127.0.0.1:8000/api/health
curl --noproxy '*' -fsS http://127.0.0.1:8000/api/config
sudo journalctl -u moa -n 100 --no-pager -o cat
```

health의 ok:true는 앱 응답 확인입니다. config에서는 speech_available, speech_engine, master_email_ready, master_password_ready를 확인합니다. 메일 준비 여부는 형식 검증 결과이므로 실제 발송까지 보장하지 않습니다. 외부 HTTPS·WebSocket·음성·영상은 브라우저로 별도 확인합니다.

```bash
# 실시간 로그 보기. Ctrl+C로 로그 보기만 종료
sudo journalctl -u moa -f -n 50 --no-pager -o cat
```

## 2 업데이트 순서

1. 방장에게 자동 기록을 끄고 대기 0건에서 회의록을 저장하도록 안내합니다.
2. 모든 회의가 끝난 시간에 DB·설정을 백업합니다. [백업 절차](화상회의_상세매뉴얼.html#section-12)를 참고하고 이전 current 경로를 기록합니다.
3. 기존 Git 다운로드 폴더의 WebConference/RelayServer로 이동합니다. 배포 폴더 /opt/moa/current에서는 git pull을 하지 않습니다.

```bash
git status --short
git pull --ff-only
git log -1 --oneline
sudo bash deploy/native/install.sh /opt/moa/python/3.12.15/bin/python3.12
```

Git 로컬 수정이나 병합 오류가 있으면 내용을 확인하고 해결한 뒤 진행합니다. installer가 성공해야 다음 점검으로 넘어갑니다. 기존 Python이 있으므로 build-python.sh를 반복 실행할 필요가 없습니다. 기존 설정·DB·키는 유지되며 Moa가 재시작됩니다.

4. 1장의 상태 명령을 실행하고 외부 브라우저에서 Ctrl+F5로 새 파일을 불러옵니다. 스마트폰에서는 페이지 새로고침 후 새 방에 입장합니다.
5. 다음 최신 기능과 기존 서비스를 확인합니다.

| 확인 | 정상 동작 |
| --- | --- |
| 통신 상태 | 보기 탭 오른쪽 5단계 색상·막대, 누르면 지연·손실·지터 |
| 웹캠 화질 | 기본 자동, 수동 360p·540p·720p·1080p, 실제 해상도 표시 |
| 회의록 | 기록 중·대기·완료 파스텔톤 안내, 대기 숫자, Word·PDF·TXT 저장 |
| 권한 | Master 직접 생성·관리, 일반 방장 이메일 승인 |
| 미디어 | 다른 네트워크 두 기기의 음성·영상 및 공유 |
| 기존 서비스 | 축전지·원격제어 응답과 CPU·메모리 사용 정상 |

새 UI가 보이지 않으면 Git 최신화만 했는지, installer가 성공했는지, 현재 릴리스의 static/media-quality.js가 존재하는지, 브라우저 캐시가 남았는지 순서대로 확인합니다. 다운로드한 Git 파일과 실제 서비스 릴리스는 별도 위치입니다.

## 3 Master 키와 설정 변경

최초 등록·분실·정기 변경에 모두 같은 명령을 사용합니다.

```bash
sudo /opt/moa/current/.venv/bin/python /opt/moa/current/scripts/set_master_key.py
```

새 키를 두 번 숨김 입력합니다. 기존 키 없이 변경할 수 있고 재시작 없이 반영됩니다. 기존 Master 관리 세션은 거부되지만 회의 연결은 유지됩니다. 웹에서 Master 인증을 다시 누릅니다. 기본과 다른 MASTER_KEY_FILE을 사용한다면 명령에도 같은 --path를 전달합니다.

일반 방장 승인용 SMTP나 음성 엔진 변경은 환경 파일을 편집한 뒤 회의가 없을 때 재시작합니다.

```bash
sudo nano /etc/moa/moa.env
sudo systemctl restart moa
```

비밀번호는 GitHub·매뉴얼·일반 로그에 넣지 않습니다. Master 비밀번호 인증과 이메일 링크 승인 권한은 별개입니다. 상세 설정은 [Master 관리](MASTER_ADMIN.md), [이메일 승인](MASTER_APPROVAL.md), [Whisper 설치](WHISPER_DEPLOY.md)를 참고하세요.

## 4 통신 상태와 화질 운영

통신 표시는 내 브라우저와 중계서버 사이의 WebRTC 추정 상태입니다. 초록 5, 파랑 4, 황금색 3, 주황 2, 빨강 1이며 회색은 측정 중입니다. 인터넷 속도계나 서버 CPU 지표는 아닙니다. 여러 경로 중 측정 가능한 가장 낮은 단계를 표시하므로 받는 쪽 문제도 반영됩니다.

자동 웹캠은 내 송신 경로를 기준으로 540p에서 시작해 360p~720p 범위에서 조절합니다. 약 3초 주기로 나쁜 상태 2회, 개선 상태 5회 연속 관측 후 바뀝니다. 수동 1080p는 실제 장치 지원과 네트워크·서버 부하를 확인하고 선택합니다. 선택값은 목표이며 네트워크 악화 시 브라우저가 전송량을 더 줄일 수 있습니다. 화면 공유에는 웹캠의 비트레이트 제한을 적용하지 않습니다.

불안정한 사용자는 화질 자동 여부, 다른 다운로드, Wi-Fi·유선 연결을 확인합니다. 여러 참석자가 동시에 불안정하면 서버 부하와 ICE·UDP·TURN 경로를 점검합니다. 웹페이지가 열린다는 사실만으로 미디어 경로가 정상이라고 판단하지 않습니다.

```bash
free -h
uptime
sudo ss -ltnup
sudo journalctl -u moa -n 100 --no-pager
```

## 5 시작과 중지 및 복구

```bash
sudo systemctl start moa          # 중지된 서비스 시작
sudo systemctl stop moa           # 현재 실행 중지. 회의 연결 종료
sudo systemctl restart moa        # 설정 적용. 회의 연결 종료
sudo systemctl enable moa         # 다음 부팅부터 자동 시작
```

서버 재시작 후 기존 회의방과 WebRTC 연결은 복구되지 않습니다. 새 방을 생성하세요. 완료된 텍스트는 DB에 남으며 다음 명령으로 종료된 방 목록을 조회할 수 있습니다.

```bash
sudo /opt/moa/current/.venv/bin/python /opt/moa/current/scripts/export_minutes.py \
  --db /var/lib/moa/meetings.db --list
```

서버 추출 CLI는 Markdown 형식이며 웹의 Word·PDF·TXT 저장 옵션과 다릅니다. 실제 추출·백업·롤백은 [통합 매뉴얼 12장](화상회의_상세매뉴얼.html#section-12)을 따르세요. 자동 기록 중이거나 처리 대기 중인 음성은 장애 시 유실될 수 있으므로 대기 0건을 확인하고 종료합니다.

## 6 장애별 다음 확인

| 증상 | 확인할 사항 |
| --- | --- |
| 새 UI가 없음 | git pull 이후 installer 실행 성공, current 릴리스, Ctrl+F5 |
| 카메라 해상도가 선택과 다름 | 웹캠 지원 해상도, 실제 설정 표시, 일부 설정 미지원 안내 |
| 회색 측정 중 유지 | WebRTC 연결 상태, 브라우저 통계 제공 여부. 양호로 간주하지 않음 |
| 통신 1~2단계 지속 | 해당 기기의 망·손실·지연, 서버 부하, ICE·TURN |
| Master 인증 503 | 키 경로와 moa 읽기 권한, 키 최초 등록 여부 |
| 이메일 인증 불가 | PUBLIC_BASE_URL·SMTP 값 및 실제 메일 전송 로그 |
| 회의록 저장 409 | 방장이 자동 기록을 끄고 대기 0건 확인 |
| Errno 97 | 서비스 RestrictAddressFamilies의 AF_NETLINK 확인 |
| apt 저장소 오류 | 오류가 난 저장소를 진단한 뒤 재시도. 관련 없는 저장소 일괄 삭제 금지 |

이 안내는 서버 변경 명령을 자동 실행하지 않습니다. 운영 정보와 인증서 갱신은 대상 서버에서 확인해야 합니다.
