# AI Blog Auto System 단계별 사용·서버 운영 매뉴얼

작성일: 2026-11-21 · Windows v1.1.0 기준 · Ubuntu API 표시 버전 0.5.0

> 먼저 Windows에서 글 한 편을 만들고 파일로 저장하세요. 서버 설치는 그 다음입니다.
> 서버 없이 글·이미지·Word·ZIP을 만들 수 있습니다. 서버는 이벤트와 콘텐츠 패키지를 받아 Android에 전달합니다.
> 현재 네이버 블로그 직접 자동 게시 기능은 없습니다. 최종 게시는 네이버 편집기에서 직접 수행합니다.

## 목차

1. [진행 순서와 준비물](#1-진행-순서와-준비물)
2. [Windows 설치·최초 실행](#2-windows-설치최초-실행)
3. [무료로 정상 동작 확인](#3-무료로-정상-동작-확인)
4. [실제 AI 글 한 편 작성](#4-실제-ai-글-한-편-작성)
5. [이미지·파일 저장·뉴스 출처 사용](#5-이미지파일-저장뉴스-출처-사용)
6. [자동 작성과 예약 실행](#6-자동-작성과-예약-실행)
7. [Ubuntu 소스 준비](#7-ubuntu-소스-준비)
8. [Ubuntu 시험 서버 실행](#8-ubuntu-시험-서버-실행)
9. [도메인 없이 Windows 연결 시험](#9-도메인-없이-windows-연결-시험)
10. [systemd 상시 서비스 설치](#10-systemd-상시-서비스-설치)
11. [HTTPS 설치와 인증서 갱신](#11-https-설치와-인증서-갱신)
12. [Windows 연결·업로드 확인](#12-windows-연결업로드-확인)
13. [매일 상태 확인·중지·재시작](#13-매일-상태-확인중지재시작)
14. [오류별 해결 순서](#14-오류별-해결-순서)
15. [데이터·백업·업데이트](#15-데이터백업업데이트)
16. [최종 점검표와 검증 범위](#16-최종-점검표와-검증-범위)

## 1. 진행 순서와 준비물

### 1-1. 어느 단계까지 진행해야 하나요?

| 목적 | 진행할 절 |
|---|---|
| 프로그램이 작동하는지만 확인 | 2~3절 |
| AI로 글 작성·파일 저장 | 2~5절 |
| 자동으로 글·이미지·ZIP 생성 | 6절까지 |
| Ubuntu에 이벤트·ZIP 보내기 시험 | 7~9절, 12절 |
| 서버 재부팅 후에도 상시 운영 | 10~13절 |

### 1-2. 준비물

| 구분 | 준비할 것 |
|---|---|
| 무료 점검 | Windows PC, v1.1.0 프로그램 |
| 실제 AI 작성 | 사용할 수 있는 OpenAI API 키·모델 |
| 서버 시험 | SSH 접속 가능한 Ubuntu, sudo 권한, Python 3.10 이상 |
| 원격 HTTPS 운영 | 실제 도메인, DNS 설정 권한, 외부 TCP 80·443 연결 |

이 매뉴얼의 Ubuntu 명령은 Bash 터미널용입니다. Windows 명령은 PowerShell이라고 별도 표시합니다.
`사용자`, `서버주소`, `blog.example.com`은 그대로 사용하지 말고 자신의 값으로 바꿉니다.
명령이 실패하면 다음 블록으로 넘어가지 말고 해당 절의 정상 결과부터 확인하세요.

### 1-3. 키와 주소 구분

| 항목 | 용도 | 어디에 입력? |
|---|---|---|
| OpenAI API 키 | 실제 글·이미지 생성 | Windows 설정의 OpenAI API 키 |
| 서버 토큰 | Windows가 Ubuntu API를 사용할 권한 | Windows 서버 토큰, Ubuntu BLOG_DEVICE_TOKEN에 같은 값 |
| SSH 계정·암호/키 | Ubuntu 관리 접속 | SSH 접속 시 |
| 기기 ID | 이벤트를 보낸 PC의 이름 | Windows 설정, 예: WINDOWS-PC-01 |

이 값들은 서로 다릅니다. 토큰·API 키를 로그나 공개 문의에 붙여넣지 마세요.

## 2. Windows 설치·최초 실행

### STEP 1. 배포 ZIP 압축 풀기

프로젝트의 `release\v1.1.0\AI-Blog-Auto-Windows-v1.1.0-x64.zip`을 새 폴더에 **전체 압축 해제**합니다.
이미 프로젝트가 있다면 `release\v1.1.0\AI-Blog-Auto\AI-Blog-Auto.exe`를 바로 실행할 수 있습니다.

```text
AI-Blog-Auto/
  AI-Blog-Auto.exe
  _internal/
```

EXE만 따로 옮기면 안 됩니다. `_internal` 폴더를 함께 유지하세요.

**정상 결과:** 창 제목에 `AI Blog Auto System · v1.1.0`이 표시됩니다.

- [ ] ZIP 전체를 압축 해제했다.
- [ ] v1.1.0 창이 열렸다.

### STEP 2. 최초 설정 마법사

마법사가 나오지 않으면 기존 Windows 사용자 설정을 읽은 것입니다. 3절로 이동하세요.

| 화면 | 입력/버튼 |
|---|---|
| 로컬 작업 공간 | 다음 |
| 서버 연결 | 주소 `http://127.0.0.1:8000`, 기기 ID `WINDOWS-DESKTOP` 유지 |
| 서버 토큰 | 지금은 비워두고 다음 |
| AI 설정 | API 키는 비워두고 Mock 체크 |
| 마지막 | 완료/Finish |

서버 주소가 있어도 서버가 실행 중일 필요는 없습니다. **서버 연결 버튼을 누르지 않아도 됩니다.**

**정상 결과:** 대시보드가 열립니다.

## 3. 무료로 정상 동작 확인

### STEP 3. 자동 작성 전체 흐름 점검

1. 왼쪽 **대시보드**를 누릅니다.
2. **무료 Mock 자동 작성 점검**을 누릅니다.
3. 글 생성 → 이미지 생성·첨부 → 파일 저장이 끝날 때까지 기다립니다.
4. 최근 자동 작성 상태가 `completed`인지 확인합니다.
5. **최근 자동 작성 결과 폴더 열기**를 누릅니다.

**정상 결과:** UUID 모양의 이름을 가진 ZIP 파일이 있습니다. 테스트용 글과 이미지가 생성됩니다.
Mock 점검은 네트워크·API 키·서버 토큰이 필요 없고 실제 AI를 호출하지 않습니다.
기존 실제/Mock 설정도 바꾸지 않습니다.

### STEP 4. 결과 파일 직접 확인

ZIP을 새 폴더에 압축 해제하고 확인합니다.

| 파일 | 확인 방법 |
|---|---|
| `article.docx` | Word 또는 호환 프로그램으로 글과 이미지 확인 |
| `index.html` | 브라우저로 열기. 이미지 폴더도 함께 압축 해제해야 함 |
| `article.txt` | 메모장에서 글 확인 |
| `manifest.json` | 패키지 ID·파일 목록·이미지 순서 정보 |
| 이미지 파일 | ZIP 내 이미지 확인 |

기본 저장 경로는 `%LOCALAPPDATA%\AI Blog Auto System\pending-packages`입니다.
Windows 탐색기 주소창에 붙여넣으면 됩니다. `BLOG_GUI_DATA_DIR` 환경변수를 따로 설정한 경우 저장 위치는 달라집니다.

- [ ] 상태가 `completed`다.
- [ ] ZIP이 존재한다.
- [ ] 문서와 이미지가 열린다.

여기까지 성공하면 **Windows 로컬 자동 작성 흐름이 정상**입니다. Mock 결과는 실제 AI 글로 사용하지 마세요.

## 4. 실제 AI 글 한 편 작성

### STEP 5. 설정 저장

왼쪽 **설정**에서 아래 항목을 입력합니다.

| 항목 | 첫 시험 값 |
|---|---|
| 서버 주소·기기 ID | 기본값 유지 |
| 서버 토큰 | 비워도 됨 |
| OpenAI API 키 | 자신의 API 키 |
| 실행 모드 | **Mock 체크 해제** |
| 글 모델 | 프로젝트 기본값 `gpt-4.1-mini` 또는 계정에서 사용 가능한 호환 모델 |
| 이미지 모델 | 프로젝트 기본값 `gpt-image-1` 또는 계정에서 사용 가능한 호환 모델 |
| 뉴스 RSS | 지금은 비워둠 |
| 글 스타일 | 아래 예시 |

```text
초보자가 이해하기 쉬운 한국어로 작성해주세요.
짧은 문단과 소제목을 사용해주세요.
사실과 의견을 구분하고 확인되지 않은 내용은 단정하지 마세요.
실용적인 예시를 포함하고 과장된 표현을 피해주세요.
```

**설정 저장**을 누릅니다. API 키 입력란이 비워져도 정상입니다. `OpenAI 키: 저장됨`을 확인하세요.
빈 키 입력란으로 다시 저장하면 기존 키를 유지합니다. 삭제하려면 **API 키 삭제**를 사용합니다.
서버 토큰도 동일한 방식이며 키·토큰은 Windows 자격증명 저장소에 보관됩니다.

**정상 결과:** Mock 체크 해제, OpenAI 키 저장됨. 실제 API 요청은 요금이 발생할 수 있습니다.

### STEP 6. 주제 입력

1. 왼쪽 **AI 글쓰기**를 누릅니다.
2. 주제 입력란에 다음 예시를 넣습니다.

```text
집에서 처음 식물을 키우는 사람을 위한 관리 방법.
물 주기, 햇빛, 통풍을 중심으로 설명하고 초보자가 자주 하는 실수와 예시를 포함해주세요.
```

3. `출처 없음 · 일반 설명 초안`인지 확인합니다.
4. 출처가 선택돼 있으면 **출처 선택 해제**를 누릅니다.
5. **AI 글 생성**을 누릅니다.

출처를 선택하지 않았다면 출처 검토 체크는 필요 없습니다.

**정상 결과:** 제목, 제목 후보 3개, 요약, 본문, 태그가 표시됩니다. 실제 생성 결과에는 `[MOCK]` 표시가 없어야 합니다.

현재 개별 AI 글쓰기·이미지 생성은 키가 없으면 Mock으로 대체됩니다. 반면 **자동 작성 버튼/예약 실행은 실제 모드에서 키가 없으면 오류로 중단**합니다.
따라서 결과의 Mock 표시를 반드시 확인하세요.

### STEP 7. 글 저장

| 원하는 동작 | 누를 버튼 |
|---|---|
| 본문 복사 | AI 글쓰기 → 본문 복사 |
| 텍스트 파일 | AI 글쓰기 → 텍스트 저장 |
| Word 파일 | 콘텐츠 출력 → Word 저장 |
| HTML 파일 | 콘텐츠 출력 → HTML 저장 |
| ZIP 파일 | 콘텐츠 출력 → ZIP 패키지 만들기 |

파일 저장창에서 경로를 선택하고 저장합니다. 개별 **AI 글 생성**만으로 Word/ZIP이 자동 생성되는 것은 아닙니다.
이전 글은 AI 글쓰기 화면의 이력 선택 상자에서 다시 열 수 있습니다.
개별 글쓰기에서 같은 주제·출처·스타일·모드·모델이면 기존 글을 재사용할 수 있습니다.

- [ ] 키가 저장됐다.
- [ ] 실제 생성 글에 Mock 표시가 없다.
- [ ] 텍스트 또는 Word로 저장했다.

## 5. 이미지·파일 저장·뉴스 출처 사용

### STEP 8. 이미지 만들고 글에 붙이기 — 선택

1. **이미지 생성**에서 이미지 설명을 입력합니다.
2. 크기를 선택하고 **이미지 생성 / 재시도**를 누릅니다.
3. 생성된 이미지를 확인합니다.
4. **AI 글쓰기**에서 이미지를 붙일 글을 선택합니다.
5. **콘텐츠 출력 → 최근 생성 이미지 추가**를 누릅니다.
6. 이미지 목록과 HTML 미리보기에서 첨부를 확인한 뒤 Word/ZIP을 저장합니다.

개별 이미지 생성에서는 글에 자동 첨부되지 않습니다. 6절 자동 작성에서 이미지 옵션을 켜면 자동 첨부됩니다.
첫 이미지는 썸네일 위치, 나머지는 본문 뒤에 순서대로 배치됩니다.

### STEP 9. RSS 뉴스 출처로 글 쓰기 — 선택

1. 설정의 **뉴스 RSS**에 사용 가능한 **HTTPS RSS/Atom 피드 주소**를 한 줄에 하나씩 입력합니다.
2. Mock을 해제하고 설정을 저장합니다.
3. **뉴스 수집 → 뉴스 수집**을 누릅니다.
4. 목록에서 기사를 선택하고 **선택 출처 열기**로 원문을 확인합니다.
5. **선택 뉴스를 글쓰기로**를 누릅니다.
6. **선택한 출처와 요약을 검토했습니다**를 체크하고 **AI 글 생성**을 누릅니다.

일반 홈페이지/기사 주소와 RSS 주소는 다릅니다. Mock 뉴스를 실제 AI 생성의 출처로 사용하면 차단됩니다.
RSS는 제목·요약 중심이며 사실 검증을 대신하지 않습니다.

## 6. 자동 작성과 예약 실행

### STEP 10. 자동 작성 설정

왼쪽 **예약 스케줄**에서 다음을 설정합니다.

| 항목 | 예시 |
|---|---|
| 시간 | `08:00, 19:00` — 쉼표 구분, 24시간 HH:MM |
| 요일 | 원하는 요일을 최소 하나 선택 |
| 주제 | 자동으로 작성할 주제 |
| 재개 정책 | 처음에는 누락된 작업 건너뛰기 |
| 초안과 이미지 함께 생성 | 이미지가 필요하면 체크 |

**예약 설정 저장**을 누릅니다. 이 주제는 AI 글쓰기 화면에서 직접 입력하는 주제와 별개입니다.

### STEP 11. 예약 시각까지 기다리지 않고 시험

**저장된 예약 작업 지금 실행**을 누릅니다. 대시보드의 **저장된 설정으로 자동 작성**도 같은 흐름입니다.

```text
저장된 주제로 새 글 생성
  → 이미지 옵션을 켠 경우 이미지 생성·첨부
  → HTML·Word·텍스트·이미지를 ZIP으로 저장
  → 대시보드 상태 completed
```

서버 접속은 수행하지 않습니다. 서버 이벤트는 로컬 대기열에 저장합니다.
같은 주제를 반복 실행해도 새 초안 ID를 만들지만, AI 문장의 차이 자체를 보장하지는 않습니다.
이미지/출력 단계가 실패해도 먼저 저장된 초안은 글쓰기 이력에서 확인할 수 있습니다.
이 자동 작성은 저장된 주제의 일반 설명 초안이며, 최신 RSS 뉴스를 자동 선정하는 기능은 아닙니다.

### STEP 12. 예약 ON

1. 즉시 실행이 성공했으면 **예약 ON / OFF**를 누릅니다.
2. 화면에 **예약 ON · 다음 실행**과 날짜·시간이 표시되는지 확인합니다.
3. 프로그램과 PC를 켜둡니다. Windows 절전 중에는 실행되지 않습니다.
4. 종료하려면 진행 중인 작업이 끝난 뒤 창을 닫습니다.

시간대는 **Asia/Seoul**입니다. 다른 작업이 진행 중인 예약 시점에는 해당 예약을 건너뛰고 경고를 남깁니다.
재개 정책의 ‘누락 작업 1회 실행’은 앱을 다시 시작할 때 적용됩니다. 모든 누락 작업을 재생하지 않습니다.
무료 Mock 점검의 성공만으로 실제 API 계정/모델이 검증된 것은 아닙니다.

- [ ] 즉시 자동 작성이 완료됐다.
- [ ] ZIP에 선택한 이미지가 포함됐다.
- [ ] 예약 ON과 다음 시각을 확인했다.

## 7. Ubuntu 소스 준비

이제부터 서버가 필요한 경우에만 진행합니다. **7~9절은 시험 실행, 10절은 상시 운영**입니다.

### STEP 13. SSH 접속과 Python 확인

Windows PowerShell:

```powershell
ssh 사용자@서버주소
```

접속한 Ubuntu 터미널:

```bash
sudo apt update
sudo apt install -y python3 python3-venv git curl ca-certificates
python3 --version
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 이상이 필요합니다"'
```

**정상 결과:** Python 3.10 이상, 마지막 명령 오류 없음.
Python 3.8이라면 여기서 멈추고 호환 Python·venv를 준비하세요. 시스템 Python을 임의로 교체하지 마세요.
상시 서비스의 Python은 `/usr/bin/python3`처럼 서비스 계정이 접근 가능한 위치에 있어야 합니다.

### STEP 14. 현재 Windows 소스를 서버로 복사

이번 수정은 로컬 작업 파일입니다. **GitHub에 푸시되지 않았다면 clone만으로 최신 코드를 받을 수 없습니다.**
정확히 현재 코드를 설치하려면 Windows의 프로젝트 폴더에서 다음과 같이 서버 파일만 묶습니다.

Windows PowerShell, 프로젝트 루트에서 실행:

```powershell
Set-Location 'C:\Users\Administrator\Downloads\proj\GITHUB\work\AI_Blog_Auto_System_Phase1\ai-blog-auto-system'
tar -czf release/v1.1.0/AI-Blog-Ubuntu-manual-source.tar.gz ubuntu-server/app ubuntu-server/deploy ubuntu-server/requirements.txt ubuntu-server/requirements-fcm.txt ubuntu-server/backup_metadata.py ubuntu-server/backup-excludes.txt shared MANUAL.md
scp release/v1.1.0/AI-Blog-Ubuntu-manual-source.tar.gz 사용자@서버주소:~/
```

이 명령은 `.env`, 데이터베이스, Windows 키·콘텐츠를 포함하지 않습니다.

Ubuntu 터미널:

```bash
mkdir -p ~/ai-blog-server-v1.1.0
tar -xzf ~/AI-Blog-Ubuntu-manual-source.tar.gz -C ~/ai-blog-server-v1.1.0
cd ~/ai-blog-server-v1.1.0
ls ubuntu-server/app/main.py ubuntu-server/deploy/ai-blog.service shared/event-schema.json
```

**정상 결과:** 세 파일이 모두 나옵니다. 아래 시험 명령은 이 폴더에서 실행합니다.
기존 폴더에 수정/운영 데이터가 있다면 새 이름의 폴더를 사용하세요.

대안으로 코드가 푸시된 것을 확인한 경우 다음 저장소를 clone할 수 있습니다.

```bash
mkdir -p ~/src
cd ~/src
git clone https://github.com/forlovesea/work.git
cd work/AI_Blog_Auto_System_Phase1/ai-blog-auto-system
git rev-parse HEAD
```

이 대안을 사용했다면 이후 `~/ai-blog-server-v1.1.0` 대신 위 프로젝트 경로를 사용합니다.

## 8. Ubuntu 시험 서버 실행

### STEP 15. 가상환경과 의존성

Ubuntu의 소스 루트에서:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r ubuntu-server/requirements.txt
mkdir -p data/metadata data/packages
chmod 700 data data/metadata data/packages
```

**정상 결과:** pip 설치 완료, data 폴더 존재. 이전 Python 버전으로 만든 `.venv`는 새 Python 설치만으로 변경되지 않습니다.

### STEP 16. 시험용 환경파일을 한 번만 만들기

아래는 토큰과 데이터 경로를 `ubuntu-server/.env`에 저장합니다. 기존 파일이 있으면 덮어쓰지 않고 중단합니다.

```bash
umask 077
.venv/bin/python - <<'PY'
from pathlib import Path
import secrets
root = Path.cwd()
with (root / 'ubuntu-server/.env').open('x', encoding='utf-8') as f:
    f.write('BLOG_DEVICE_TOKEN=' + secrets.token_urlsafe(32) + '\n')
    f.write('BLOG_DB_PATH=' + str(root / 'data/metadata/events.sqlite3') + '\n')
    f.write('BLOG_PACKAGE_DIR=' + str(root / 'data/packages') + '\n')
    f.write('BLOG_PACKAGE_MAX_BYTES=104857600\n')
print('환경파일 생성 완료. 토큰은 파일에서 확인하세요.')
PY
chmod 600 ubuntu-server/.env
nano ubuntu-server/.env
```

편집기에서 `BLOG_DEVICE_TOKEN=` 뒤의 값을 확인하여 개인 비밀 저장소에 보관합니다. Windows의 서버 토큰에도 같은 값을 넣습니다.
`nano`는 Ctrl+X로 닫습니다. 파일이 이미 있다면 생성 코드를 다시 실행하지 말고 기존 파일을 확인하세요.

앱이 이 `.env`를 읽습니다. 같은 SSH 세션에서 이전 `BLOG_*` 환경변수를 export한 적이 있으면 해당 값이 파일보다 우선하므로 새 SSH 세션에서 시험하는 편이 명확합니다.

### STEP 17. 서버 실행 — 터미널 A

```bash
cd ~/ai-blog-server-v1.1.0
.venv/bin/python -m uvicorn app.main:app --app-dir ubuntu-server --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

**정상 결과:** `Application startup complete`, `127.0.0.1:8000` 안내. 이 터미널은 실행 상태로 유지합니다.
종료는 Ctrl+C입니다. SSH를 끊어도 유지하려면 10절의 systemd를 사용합니다.

### STEP 18. 실행·인증 확인 — 별도 Ubuntu 터미널 B

```bash
curl --fail http://127.0.0.1:8000/api/v1/health
```

**정상 결과:** `{"status":"ok","version":"0.5.0"}`. 공백 순서는 다를 수 있습니다.
서버 버전 0.5.0과 Windows 버전 1.1.0은 별도 번호이며 오류가 아닙니다.

인증도 확인합니다. 토큰 입력은 화면에 표시되지 않습니다.

```bash
read -rsp '서버 토큰: ' BLOG_CHECK_TOKEN; echo
curl --fail 'http://127.0.0.1:8000/api/v1/events?limit=1' -H "X-Device-Token: $BLOG_CHECK_TOKEN"
unset BLOG_CHECK_TOKEN
```

**정상 결과:** HTTP 오류 없이 `[]` 또는 이벤트 JSON 배열. 401은 토큰 불일치입니다.
health 성공은 토큰 인증 성공을 의미하지 않습니다.

- [ ] health 응답 status가 ok다.
- [ ] 토큰을 넣은 events 조회가 성공한다.

## 9. 도메인 없이 Windows 연결 시험

### STEP 19. SSH 터널 열기

Ubuntu 서버를 실행한 상태에서 **별도 Windows PowerShell**을 엽니다.

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18000:127.0.0.1:8000 사용자@서버주소
```

접속 후 출력 없이 대기하는 것은 정상입니다. 창을 열어둡니다.

다른 Windows PowerShell에서:

```powershell
curl.exe --fail http://127.0.0.1:18000/api/v1/health
```

**정상 결과:** status ok. Windows 프로그램 설정:

```text
서버 주소: http://127.0.0.1:18000
서버 토큰: STEP 16의 BLOG_DEVICE_TOKEN 값
기기 ID: WINDOWS-PC-01
```

설정 저장 후 12절의 연결 점검을 진행합니다. SSH 터널은 Windows 개발 시험용입니다.
Windows의 localhost는 Ubuntu가 아니라 Windows 자신입니다. 터널을 닫으면 이 주소의 연결도 종료됩니다.

## 10. systemd 상시 서비스 설치

시험을 통과한 후 진행합니다. 운영용 데이터는 시험 데이터와 분리합니다.
아래는 **새 서버에 최초 설치**하는 예시입니다. 기존 `/etc/ai-blog/server.env`나 릴리스가 있으면 덮어쓰지 말고 15절을 참고하세요.

### STEP 20. 시험 서버 종료·계정과 경로 준비

터미널 A의 Uvicorn을 Ctrl+C로 종료합니다. 8000 포트가 비었는지 확인합니다.

```bash
sudo ss -ltnp | grep ':8000' || true
getent passwd ai-blog || sudo useradd --system --user-group --home-dir /var/lib/ai-blog --shell /usr/sbin/nologin ai-blog
sudo install -d -m 755 /opt/ai-blog/releases
sudo install -d -o ai-blog -g ai-blog -m 700 /var/lib/ai-blog/metadata /var/lib/ai-blog/packages
sudo install -d -o root -g root -m 700 /etc/ai-blog
```

처음 명령에 실행 중인 다른 프로세스가 보이면 정체를 확인하고 중복 실행을 해소합니다.

### STEP 21. 소스·가상환경 설치

Ubuntu 소스 루트에서 다음을 실행합니다. 이미 같은 릴리스 폴더가 있으면 `mkdir` 오류에서 멈추고 새 릴리스명을 정하세요.

```bash
cd ~/ai-blog-server-v1.1.0
sudo mkdir /opt/ai-blog/releases/v1.1.0
sudo install -d -m 755 /opt/ai-blog/releases/v1.1.0/ubuntu-server
sudo cp -R ubuntu-server/app ubuntu-server/deploy /opt/ai-blog/releases/v1.1.0/ubuntu-server/
sudo cp ubuntu-server/requirements.txt ubuntu-server/requirements-fcm.txt ubuntu-server/backup_metadata.py ubuntu-server/backup-excludes.txt /opt/ai-blog/releases/v1.1.0/ubuntu-server/
sudo cp -R shared /opt/ai-blog/releases/v1.1.0/
sudo chmod -R a+rX /opt/ai-blog/releases/v1.1.0
sudo /usr/bin/python3 -m venv /opt/ai-blog/releases/v1.1.0/.venv
sudo /opt/ai-blog/releases/v1.1.0/.venv/bin/python -m pip install -r /opt/ai-blog/releases/v1.1.0/ubuntu-server/requirements.txt
```

**정상 결과:** 의존성 설치 성공. 시스템 Python이 3.10 이상이어야 합니다.
개인 홈에 설치된 Python은 서비스의 `ProtectHome=true` 때문에 사용할 수 없는 경우가 있습니다.

### STEP 22. 운영 환경파일 생성

시험과 별개의 새 토큰을 생성합니다. Windows 설정에도 새 값을 저장해야 합니다.
기존 파일이 있으면 `open('x')`가 중단하므로 재설치로 토큰을 덮어쓰지 않습니다.

```bash
sudo python3 - <<'PY'
from pathlib import Path
import os, secrets
os.umask(0o077)
with Path('/etc/ai-blog/server.env').open('x', encoding='utf-8') as f:
    f.write('BLOG_DEVICE_TOKEN=' + secrets.token_urlsafe(32) + '\n')
    f.write('BLOG_DB_PATH=/var/lib/ai-blog/metadata/events.sqlite3\n')
    f.write('BLOG_PACKAGE_DIR=/var/lib/ai-blog/packages\n')
    f.write('BLOG_PACKAGE_MAX_BYTES=104857600\n')
print('운영 환경파일 생성 완료')
PY
sudo chmod 600 /etc/ai-blog/server.env
sudo nano /etc/ai-blog/server.env
```

토큰 값을 개인 비밀 저장소에 보관합니다. 기본 이벤트·패키지 서버에는 OpenAI 키가 필요하지 않습니다.
OpenAI 요청은 Windows에서 수행합니다. FCM은 별도 설정 항목이며 이 기본 설치에는 필요 없습니다.

### STEP 23. 서비스 등록·시작

처음 설치에는 `/opt/ai-blog/current`가 없어야 합니다. 이미 있으면 15절의 업데이트 절차를 사용하세요.

```bash
sudo ln -s /opt/ai-blog/releases/v1.1.0 /opt/ai-blog/current
sudo install -m 644 /opt/ai-blog/current/ubuntu-server/deploy/ai-blog.service /etc/systemd/system/ai-blog.service
sudo systemd-analyze verify /etc/systemd/system/ai-blog.service
sudo systemctl daemon-reload
sudo systemctl enable --now ai-blog
systemctl is-active ai-blog
systemctl is-enabled ai-blog
curl --fail http://127.0.0.1:8000/api/v1/health
```

**정상 결과:** `active`, `enabled`, status ok.
`systemd-analyze verify`에서 오류가 나면 서비스 시작 전에 수정하세요.

실패하면:

```bash
sudo systemctl status ai-blog --no-pager -l
sudo journalctl -u ai-blog -n 100 --no-pager
```

- [ ] 서비스가 active다.
- [ ] 부팅 자동 시작이 enabled다.
- [ ] 루프백 health가 성공한다.

## 11. HTTPS 설치와 인증서 갱신

### STEP 24. 도메인·포트 확인

연결 구조는 다음과 같습니다.

```text
Windows/Android -- HTTPS 443 --> Nginx -- HTTP 127.0.0.1:8000 --> Uvicorn
```

| 포트 | 역할 |
|---|---|
| SSH 포트, 보통 22 | 관리자 접속. 실제 SSH 설정에 맞춤 |
| 80 | 인증서 발급·갱신, HTTPS 이동 |
| 443 | Windows/Android 접속 |
| 8000 | 서버 내부 전용. 외부 공개하지 않음 |

도메인의 A 레코드는 서버의 실제 공개 IPv4를 가리켜야 합니다. AAAA가 있다면 IPv6도 올바르게 연결되어야 합니다.
클라우드 보안 그룹·공유기 포트 전달·방화벽에서 80/443을 허용합니다. SSH 접속을 유지하세요.

Ubuntu:

```bash
BLOG_DOMAIN=blog.example.com
getent ahosts "$BLOG_DOMAIN"
sudo apt install -y nginx certbot
sudo install -d -m 755 /var/www/ai-blog-acme
sudo systemctl enable --now nginx
```

`BLOG_DOMAIN`은 자신의 도메인으로 바꿉니다. 새 터미널을 열면 다시 지정해야 합니다.
기존 Nginx 사이트가 있다면 백업하고 동일 도메인의 중복 server 블록부터 확인합니다.

### STEP 25. 인증서 발급용 설정 적용

아직 인증서 파일이 없으므로 최종 TLS 설정부터 적용하면 안 됩니다.

```bash
cd /opt/ai-blog/current
sed "s/blog-monitor.example.com/$BLOG_DOMAIN/g" ubuntu-server/deploy/nginx-bootstrap.conf.example | sudo tee /etc/nginx/sites-available/ai-blog >/dev/null
sudo ln -sfn /etc/nginx/sites-available/ai-blog /etc/nginx/sites-enabled/ai-blog
sudo nginx -t && sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/ai-blog-acme --cert-name "$BLOG_DOMAIN" -d "$BLOG_DOMAIN"
```

Certbot의 이메일·약관 안내를 완료합니다.
**정상 결과:** 인증서 발급 성공. 실패하면 DNS와 외부 80 포트부터 확인합니다.
기존 인증서가 있다면 `sudo certbot certificates`로 실제 인증서 이름과 경로를 확인하세요.

### STEP 26. HTTPS 프록시 적용

```bash
sed "s/blog-monitor.example.com/$BLOG_DOMAIN/g" ubuntu-server/deploy/nginx.conf.example | sudo tee /etc/nginx/sites-available/ai-blog >/dev/null
sudo nginx -t && sudo systemctl reload nginx
curl --fail "https://$BLOG_DOMAIN/api/v1/health"
```

**정상 결과:** Nginx 설정 검사 성공, 인증서 오류 없이 status ok.
`https://서버:8000`으로 연결하지 마세요. 기본 Uvicorn 8000에는 TLS가 없습니다.
앱은 리디렉션을 따라가지 않으므로 처음부터 HTTPS 주소를 입력합니다.

### STEP 27. 인증서 자동 갱신 확인

```bash
sudo install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nnginx -t && systemctl reload nginx\n' | sudo tee /etc/letsencrypt/renewal-hooks/deploy/ai-blog-nginx >/dev/null
sudo chmod 755 /etc/letsencrypt/renewal-hooks/deploy/ai-blog-nginx
sudo systemctl enable --now certbot.timer
sudo certbot renew --dry-run
systemctl list-timers --all | grep certbot
```

**정상 결과:** 갱신 시험 성공, 타이머 표시. webroot 갱신을 위해 80 포트와 challenge 경로를 유지합니다.
위 명령은 Ubuntu apt로 Certbot을 설치한 경로 기준입니다.

### STEP 28. Windows에서 외부 접속 확인

Windows PowerShell:

```powershell
curl.exe --fail https://blog.example.com/api/v1/health
```

자신의 도메인으로 바꿔 실행합니다. **정상 결과:** 인증서 오류 없이 status ok.
서버 안에서만 성공하고 Windows에서 실패하면 외부 DNS·방화벽·포트 전달을 확인하세요.

- [ ] 외부 Windows에서 HTTPS health가 성공했다.
- [ ] 인증서 갱신 시험이 성공했다.
- [ ] 8000은 외부에 공개하지 않았다.

## 12. Windows 연결·업로드 확인

### STEP 29. Windows 서버 설정

| 항목 | 원격 HTTPS 운영 | SSH 터널 시험 |
|---|---|---|
| 서버 주소 | `https://자신의도메인` | `http://127.0.0.1:18000` |
| 서버 토큰 | STEP 22 운영 토큰 | STEP 16 시험 토큰 |
| 기기 ID | `WINDOWS-PC-01` | 같은 규칙 |

주소에 `/api/v1`, `/docs`를 붙이지 않습니다. 토큰에는 `BLOG_DEVICE_TOKEN=`을 제외한 값만 입력합니다.
설정 저장 후 키 입력란이 비워지는 것은 정상입니다.

### STEP 30. 연결·이벤트 시험

1. **서버 연결 → 연결 / 이벤트 조회**를 누릅니다.
2. `ONLINE · 인증된 API 연결 확인`인지 확인합니다.
3. **Mock 이벤트 전송**을 누릅니다.
4. 서버가 1건을 확인했다는 메시지를 확인합니다.
5. 다시 **연결 / 이벤트 조회**로 이벤트 목록을 확인합니다.

Mock 모드여도 이 버튼은 실제 서버에 접속합니다. 이벤트 대기열이 이미 있으면 전송 건수는 더 많을 수 있습니다.

### STEP 31. 콘텐츠 패키지 전송

| 상황 | 동작 |
|---|---|
| 자동 작성으로 ZIP을 이미 만든 경우 | 콘텐츠 출력 → 대기 업로드 재시도 |
| 개별 글쓰기로 만든 글을 전송 | 글쓰기 이력에서 선택 → 콘텐츠 출력 → 수동 발행 패키지 생성·업로드 |

‘대기 업로드 재시도’는 **모든 미전송 대기 ZIP**을 대상으로 하므로 무료 Mock 점검 결과도 포함됩니다.
서버가 없거나 연결이 끊겨도 로컬 초안·대기 ZIP은 유지됩니다. 연결 복구 후 재시도합니다.
이벤트만 보내려면 서버 연결의 **대기 이벤트 재전송**을 사용합니다.

**정상 결과:** 업로드 완료/전달 완료 메시지. Ubuntu에서 목록도 확인할 수 있습니다.

```bash
read -rsp '운영 서버 토큰: ' BLOG_CHECK_TOKEN; echo
curl --fail http://127.0.0.1:8000/api/v1/packages -H "X-Device-Token: $BLOG_CHECK_TOKEN"
unset BLOG_CHECK_TOKEN
```

서버 패키지는 업로드 후 48시간부터 다운로드가 거부됩니다. PC에 저장된 원본은 별도로 남습니다.
패키지 재시도는 최초 ZIP을 재사용합니다. 업로드 후 내용을 바꿔 전달하려면 새 자동 작성 등으로 새 초안 ID를 만드세요.
로그 관리 화면의 일반 로그 전체는 서버로 자동 전송되지 않습니다. 서버에는 별도의 이벤트가 전달됩니다.

### STEP 32. Android 연결 — 선택

Ubuntu에서 운영 토큰으로 일회용 페어링 코드를 발급합니다.

```bash
read -rsp '운영 서버 토큰: ' BLOG_CHECK_TOKEN; echo
curl --fail -X POST http://127.0.0.1:8000/api/v1/pairing/codes -H "X-Device-Token: $BLOG_CHECK_TOKEN"
unset BLOG_CHECK_TOKEN
```

Android에 같은 HTTPS 서버 주소와 응답의 `code`를 입력하여 페어링합니다.
유효시간은 `expires_at`을 확인합니다. 기기에 관리자 토큰을 직접 넣는 방식과 구분하세요.
상세 Android 사용법은 프로젝트의 `docs/android-install-use.md`를 참고하세요.

## 13. 매일 상태 확인·중지·재시작

### 13-1. 최소 일일 점검

Ubuntu:

```bash
systemctl is-active ai-blog
systemctl is-active nginx
curl --fail http://127.0.0.1:8000/api/v1/health
curl --fail https://blog.example.com/api/v1/health
sudo journalctl -u ai-blog -n 50 --no-pager
df -h /var/lib/ai-blog
timedatectl status
```

자신의 도메인으로 바꿉니다. 정상 기준: 두 서비스 active, 두 health 성공, 반복 오류 없음, 디스크 여유 공간 있음, 시간 동기화 정상.
Windows에서는 예약 ON/다음 실행 시각, 최근 작성 결과와 로그도 확인하세요.

### 13-2. 작업별 명령

| 목적 | Ubuntu 명령 |
|---|---|
| 상세 서비스 상태 | `sudo systemctl status ai-blog --no-pager -l` |
| 실시간 로그 보기 | `sudo journalctl -u ai-blog -f` — 종료 Ctrl+C는 로그 보기만 종료 |
| 서버 중지 | `sudo systemctl stop ai-blog` |
| 서버 시작 | `sudo systemctl start ai-blog` |
| 서버 재시작 | `sudo systemctl restart ai-blog` |
| 부팅 자동 시작 해제 | `sudo systemctl disable ai-blog` — 현재 실행은 그대로 |
| 자동 시작 해제와 즉시 중지 | `sudo systemctl disable --now ai-blog` |
| service 파일 변경 반영 | `sudo systemctl daemon-reload` 후 `sudo systemctl restart ai-blog` |
| server.env 변경 반영 | `sudo systemctl restart ai-blog` |
| Nginx 변경 반영 | `sudo nginx -t && sudo systemctl reload nginx` |
| 포트 확인 | `sudo ss -ltnp` |
| 인증서 목록 | `sudo certbot certificates` |

서버 재시작은 진행 중인 업로드가 없는 때 수행합니다. 재시작 후 health와 Windows 인증 조회를 다시 확인합니다.
시험 터미널에서 실행한 Uvicorn은 systemctl로 관리되지 않습니다. 해당 터미널에서 Ctrl+C로 종료합니다.

## 14. 오류별 해결 순서

| 증상 | 확인 및 조치 |
|---|---|
| EXE가 실행되지 않음 | ZIP 전체 압축 해제, `_internal` 동봉, 새 버전 폴더에서 실행 |
| 창 제목이 v1.1.0이 아님 | 예전 바로가기 대신 release/v1.1.0의 EXE 실행 |
| 키 저장 오류 | 로그인된 Windows 사용자 세션에서 실행. Windows 자격증명 저장소 사용 가능 여부 확인 |
| 생성 글에 MOCK 표시 | 설정 Mock 해제, API 키 저장 확인 후 다시 생성 |
| 실제 자동 작성에서 API 키 필요 오류 | 키 저장 또는 무료 Mock 점검 사용 |
| 실제 AI 401/403/모델 오류 | API 키·모델 접근 권한 확인. 서버 토큰과 혼동하지 않기 |
| 예약 실행 안 됨 | 예약 저장, ON, 요일·Asia/Seoul 시간, 앱/PC 실행·절전·진행 중 작업 확인 |
| 자동 작성 실패 | 대시보드 단계와 로그 확인. 글쓰기 이력에 부분 완료 초안이 남아 있는지 확인 |
| 이미지가 Word에 없음 | 개별 생성은 콘텐츠 출력에서 첨부 필요. 자동 작성은 이미지 옵션을 켜고 새 실행 |
| RSS 결과 없음 | HTTPS RSS/Atom 주소인지 확인. 일반 기사 URL은 피드가 아님 |
| 원격 HTTP 거부 | HTTPS 구축 또는 Windows SSH 터널 사용 |
| WRONG_VERSION_NUMBER/TLS 프로토콜 오류 | HTTPS로 HTTP 8000에 접속한 것인지 확인. Nginx 443 사용 |
| 인증서 검증 실패 | 도메인 일치, 만료, fullchain 경로, PC 시간 확인 |
| 연결 거부 | 서비스/터널 실행, 포트, DNS 확인 |
| 502/504 | Nginx 뒤 Uvicorn 실행과 내부 포트 일치 확인 |
| 서버 401 | 현재 서버 환경파일의 토큰과 Windows 토큰 비교. 토큰 변경 후 서버 재시작 |
| 404 | 올바른 Nginx 도메인 설정, 앱 URL에 /api/v1 제거 |
| 413 | 서버와 Nginx의 업로드 한도 확인. 기본 100 MiB |
| 패키지 410 | 서버 보존기간 만료. 새 초안 ID로 새 패키지 생성 |
| address already in use | 시험 Uvicorn과 systemd 중복 실행 확인 |
| systemd 203/EXEC | 가상환경 Python 경로·실행 권한·개인 홈 Python 의존 여부 확인 |
| Permission denied | ai-blog 계정의 데이터 폴더 권한, 소스 읽기 권한 확인 |
| Python 3.8 관련 타입 오류 | Python 3.10 이상으로 새 가상환경 생성 |

문제 문의 시 버전, 누른 버튼, 오류 문구, 발생 시각을 기록하세요. API 키·서버 토큰·전체 환경파일은 보내지 않습니다.

## 15. 데이터·백업·업데이트

### 15-1. 저장 위치

| 위치 | 내용 |
|---|---|
| Windows `%LOCALAPPDATA%\AI Blog Auto System` | 설정·글 이력·이미지·로컬 로그·이벤트 대기열·대기 ZIP |
| Windows Credential Manager | API 키와 서버 토큰. 폴더 복사만으로 이전되지 않음 |
| Ubuntu `/var/lib/ai-blog/metadata` | 운영 메타데이터 DB |
| Ubuntu `/var/lib/ai-blog/packages` | 운영 콘텐츠 ZIP |
| Ubuntu `/etc/ai-blog/server.env` | 운영 토큰과 경로 |
| Ubuntu `/opt/ai-blog/releases` | 서버 코드·가상환경 |

Windows는 앱 종료 후 데이터 폴더를 백업합니다. 다른 PC로 옮기면 키·토큰은 다시 설정합니다.
서버 콘텐츠 ZIP은 48시간 보존 정책 때문에 백업·스냅샷에서 제외합니다. 메타데이터는
`ubuntu-server/backup_metadata.py`의 사용법과 기존 `docs/build-and-deploy.md`를 참고하여 별도로 백업합니다.
실행 중 SQLite 파일 하나만 무조건 복사하는 방식은 피하세요. 환경파일 백업도 접근 권한을 제한합니다.

운영 메타데이터만 백업하는 예시:

```bash
sudo install -d -m 700 /var/backups/ai-blog
sudo /opt/ai-blog/current/.venv/bin/python /opt/ai-blog/current/ubuntu-server/backup_metadata.py /var/lib/ai-blog/metadata/events.sqlite3 "/var/backups/ai-blog/events-$(date +%Y%m%d-%H%M%S).sqlite3"
sudo ls -lh /var/backups/ai-blog
```

**정상 결과:** 새 SQLite 백업 파일 생성. 같은 이름의 기존 파일은 덮어쓰지 않습니다.
복구는 서비스를 중지한 뒤 별도 시험 복사본에서 검증하고 파일 소유자를 `ai-blog:ai-blog`로 맞춰 진행합니다.

### 15-2. Windows 업데이트

1. 현재 작업 완료 후 앱을 종료합니다.
2. 새 버전 ZIP을 다른 폴더에 전체 압축 해제합니다.
3. 새 EXE를 실행하고 제목의 버전을 확인합니다.
4. 같은 Windows 계정이면 기존 데이터·키를 읽습니다.
5. 무료 Mock 점검 → 실제 글쓰기 → 필요 시 서버 연결 순서로 확인합니다.

### 15-3. 서버 업데이트·복구

1. 새 소스를 `/opt/ai-blog/releases/새버전`에 별도 설치하고 해당 경로에 가상환경·의존성을 준비합니다.
2. 기존 `/etc/ai-blog/server.env`와 `/var/lib/ai-blog`를 유지합니다. 토큰을 새로 생성하지 않습니다.
3. 현재 대상은 `readlink -f /opt/ai-blog/current`로 기록합니다.
4. 업로드가 없는 때 서비스를 중지하고 `current`를 새 릴리스로 전환합니다.
5. 시작 후 health와 인증 조회, 패키지 업로드를 확인합니다.
6. 실패하면 서비스를 중지하고 이전 대상 경로로 되돌려 재시작합니다.

예시의 `새버전`은 실제 준비한 디렉터리명으로 변경합니다. `current`가 디렉터리가 아닌 심볼릭 링크인지 확인하세요.

```bash
readlink -f /opt/ai-blog/current
sudo systemctl stop ai-blog
sudo ln -sfnT /opt/ai-blog/releases/새버전 /opt/ai-blog/current
sudo systemctl start ai-blog
curl --fail http://127.0.0.1:8000/api/v1/health
```

service 파일 자체를 바꿨다면 별도 설치와 daemon-reload도 필요합니다.
롤백하면서 만료된 콘텐츠를 복구하거나 보존기간을 연장하지 않습니다.

## 16. 최종 점검표와 검증 범위

### 단계별 완료 기록

| 확인 항목 | 완료 | 확인일/메모 |
|---|---|---|
| Windows v1.1.0 실행 | [ ] | |
| 무료 Mock 점검 completed | [ ] | |
| Word·HTML·이미지 파일 확인 | [ ] | |
| 실제 AI 글쓰기 성공, Mock 표시 없음 | [ ] | |
| 자동 작성 새 초안·ZIP 생성 | [ ] | |
| 예약 ON·다음 실행 시각 확인 | [ ] | |
| Ubuntu Python 3.10+·의존성 설치 | [ ] | |
| 루프백 health와 인증 events 성공 | [ ] | |
| systemd active·enabled | [ ] | |
| 외부 Windows HTTPS health 성공 | [ ] | |
| Certbot 갱신 시험 성공 | [ ] | |
| Windows ONLINE·이벤트 전송 성공 | [ ] | |
| ZIP 업로드·서버 목록 확인 | [ ] | |
| 재시작 후 health·인증 재확인 | [ ] | |

### 이 문서가 근거로 삼은 검증

- v1.1.0 코드 자동 테스트: 106개 통과.
- 빌드한 Windows EXE 자체 시험: 서버 없는 Mock 자동 작성·이미지 첨부·ZIP·GUI 초기화 통과.
- 로컬 HTTP 시험: 이벤트, ZIP, 페어링, WebSocket 통과.
- TLS 회귀 시험은 로컬 시험 인증서로 수행. 운영 도메인 인증서를 검증한 것은 아님.
- 실제 유료 AI 요청, 대상 Ubuntu OS/systemd/Nginx, 운영 DNS/인증서, 네이버 실제 게시 시험은 별도로 수행해야 함.

문서의 설치 명령을 작성한 것과 실제 서버에 설치한 것은 다릅니다. 이 매뉴얼 작성으로 운영 서버는 변경되지 않았습니다.

### 추가 참고

- 프로젝트 내 `docs/windows-install-use.md`, `docs/ubuntu-install-use.md`, `docs/https-setup.md`
- [Ubuntu TLS 인증서 안내](https://ubuntu.com/server/docs/how-to/security/obtain-tls-certificates/)
- [Nginx WebSocket 프록시](https://nginx.org/en/docs/http/websocket.html)
- [Certbot 안내](https://certbot.eff.org/instructions?os=ubuntufocal&tab=standard&ws=other)
