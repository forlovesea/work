# Windows 호스트 검증 — 2026-10-15

현재 호스트에서 서버 시작, 한국어 Vosk 모델 로딩, WebRTC 중계 및 브라우저 기능 검증을 통과했습니다.

## 검증 결과

- `pip check`: 의존성 충돌 없음.
- 전체 pytest: **15 passed**, 6.00초. Starlette 내부의 AnyIO deprecated alias 경고 1건은 남아 있지만 테스트 실패는 없습니다.
- `/api/health`: `ok: true`.
- `/api/config`: `speech_available: true`, 오류 메시지 없음.
- 루트 `run.ps1`로 실제 서버 시작, `run.cmd --help` 정상 실행.
- Chrome headless의 독립된 3개 브라우저 컨텍스트: 입장, 영상 수신, 기본 음소거, 발표권 전환, 화이트보드 동기화, 회의록 내보내기, 방장 이전, 초대 링크/클립보드 대체 처리, 모바일 너비, JavaScript 오류 없음 확인.
- 브라우저 결과물: `RelayServer/test-results/`의 스크린샷과 `meeting-minutes.md`.

## 보완 내용 및 호스트 조건

- Windows PowerShell의 UTF-8 BOM 없는 파일 해석에 영향을 받지 않도록 루트 실행 스크립트의 한글 경로 리터럴을 제거했습니다.
- Windows 메모리 할당 여유가 부족한 상태에서 모델 로딩이 실패하면, 메모리 확보 및 서버 재시작 안내를 제공합니다. 관련 회귀 테스트를 추가했습니다.
- 앞선 실패 당시 시스템 메모리 할당 여유는 약 44MiB였고 일반 파일 읽기에서도 MemoryError가 발생했습니다. 이번 실행에서는 약 952MiB의 여유가 측정되었고 모델 로딩에 성공했습니다. 이 수치는 동시 실행 앱에 따라 변하며 권장 용량이나 부하 보장값이 아닙니다.
- 기본 pytest 임시 폴더 정리 시 기존 폴더 권한 오류가 발생하여, 프로젝트 안의 전용 임시 폴더를 지정한 재검증으로 정상 종료를 확인했습니다.

## 재검증 방법

프로젝트 루트에서 서버를 실행합니다.

```powershell
.\run.cmd
```

브라우저 접속 주소는 `http://localhost:8000`입니다. 별도 터미널에서:

```powershell
cd RelayServer
..\.venv\Scripts\python.exe -m pytest -q --basetemp=test-results/pytest-host-check
..\.venv\Scripts\python.exe scripts/browser_smoke.py
```

`--basetemp` 폴더는 pytest가 초기화하므로 테스트 전용으로만 사용하세요. 브라우저 테스트는 회의를 생성하므로 실제 회의록과 분리하려면 서버 실행 터미널에서 `DB_PATH` 환경 변수를 별도의 테스트 DB 경로로 설정하세요.

이번 검증은 별도 테스트 DB로 수행했으며 기존 회의록 DB는 변경하지 않았습니다. 테스트 서버는 종료했고 임시 DB와 모델 복사본은 정리했습니다.

실제 카메라·마이크 장치의 사용감, 한국어 발화 인식 정확도, 화면 선택 창, 외부 네트워크 HTTPS/TURN, 다수 참가자 부하 성능은 이번 검증에 포함되지 않습니다.
