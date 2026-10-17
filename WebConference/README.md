# 화상회의 프로젝트

GitHub에서 내려받아 서버를 실행하려면 **[Ubuntu 배포 안내](UBUNTU_DEPLOY.md)**를 먼저 읽으세요. 현재 서버 폴더 이름은 `RelayServer`입니다.

회의록은 [한국어 Whisper 정확도 우선 모드](WHISPER_DEPLOY.md)로 전환할 수 있습니다. 지연을 허용하고 문맥을 모아 처리하며, 기존 Vosk 모드도 유지합니다.

[회의록 저장 안내](MINUTES_EXPORT.md): Word·PDF·텍스트로 전체 대화를 저장하고, 선택하면 주제별 요약을 함께 추가합니다.

새 회의 생성에는 [Master 이메일 인증](MASTER_APPROVAL.md)이 필요합니다. 업데이트 전 SMTP 발송 설정을 준비하세요.

실제 서버 구현과 실행·배포 파일은 **[중계서버](RelayServer/README.md)** 디렉토리에 있습니다.

## 상세 사용 매뉴얼

**[통합 HTML 매뉴얼 열기](화상회의_상세매뉴얼.html)** — 일반 참여자·방장 사용법, Ubuntu 서버 설치와 실행, 부팅 자동 시작, Windows 작업 스케줄러, 백업과 장애 대응을 담았습니다.

수정 가능한 원문은 [매뉴얼 안내](매뉴얼/00_매뉴얼_안내.md)에서 역할별로 읽을 수 있습니다. 문서 작성만으로 서버 설치나 자동 시작 등록이 실행되는 것은 아닙니다.

```text
화상회의/
├─ RelayServer/
│  ├─ server.py           Python 서버 실행 진입점
│  ├─ app/                영상·음성 중계, 방·발표권 관리, 회의록
│  ├─ static/             서버가 제공하는 브라우저 클라이언트
│  ├─ models/             한국어 음성 인식 모델
│  ├─ data/               기존 회의록 SQLite 데이터
│  ├─ deploy/             HTTPS·TURN 설정
│  ├─ run.ps1             Windows 실행
│  ├─ run.cmd             Windows 실행 (PowerShell 정책 변경 불필요)
│  └─ run.sh              Linux 실행
├─ .venv/                 현재 PC에서 사용하는 개발용 Python 환경
└─ run.ps1                RelayServer/run.ps1로 연결하는 실행 파일
```

## 현재 PC에서 실행

`화상회의` 디렉토리에서:

```powershell
.\.venv\Scripts\python.exe .\RelayServer\server.py
```

또는 `RelayServer` 디렉토리에서:

```powershell
.\run.cmd
# 다른 포트 사용:
.\run.cmd --port 8080
```

루트 디렉토리에서도 `.\run.cmd`로 실행할 수 있습니다. 종료는 실행 창에서 `Ctrl+C`를 누릅니다.

브라우저에서 http://localhost:8000 에 접속합니다. 실행 스크립트는 현재 설치된 상위 `.venv`를 자동으로 사용합니다. 이전 PC에서 복사된 가상환경은 제거하고 현재 PC의 Python 3.12로 다시 생성했습니다.

가상환경 재구성이 필요하면 프로젝트 루트에서 다음을 실행합니다. 시스템 실행 정책은 변경하지 않고 해당 설치 프로세스에만 적용합니다. 별도 Python 3.12를 사용하려면 `-Python 'python.exe의 전체 경로'`를 덧붙이세요.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

한국어 음성 인식 모델과 기존 `RelayServer/data`의 회의록은 보존했습니다. 로컬 실행은 기본 설정을 사용합니다. Ubuntu 운영 설정 예제는 `RelayServer/deploy/native/moa.env.example`에 있습니다.

PowerShell 스크립트 실행이 허용된 환경에서는 기존처럼 `.\run.ps1`도 사용할 수 있습니다. 현재 PC에서는 실행 정책 때문에 `.ps1`이 차단되므로 위 Python 명령 또는 `RelayServer/run.cmd`를 사용하세요.

## Ubuntu로 옮길 때

`RelayServer` 폴더를 서버에 복사한 뒤 그 폴더의 [배포 설명서](RelayServer/README.md)를 따르세요. 기존 Windows `.venv`는 복사하지 않습니다. Ubuntu에서는 [직접 설치 안내](UBUNTU_DEPLOY.md)에 따라 별도 Python 3.12와 systemd 서비스를 설치합니다.

서버 주소와 접속 ID 설정, 기본 마이크·스피커 꺼짐, 두 가지 회의 모드, 발표권 제어, 다중 화면·발표자·화이트보드·화면 공유 기능은 서버가 제공하는 브라우저 화면에서 사용할 수 있습니다.
