# Weekly Total System

## 실행 (Windows / VS Code)

1. VS Code에서 이 폴더(`weekly_total_system`)를 엽니다.
2. Python 및 Python Debugger 확장을 설치합니다.
3. 처음 설정할 때 터미널에서 아래 명령을 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. `Ctrl + F5`를 누르면 `weekly_report_main.py`의 로그인 창이 열립니다.
   실행 구성을 선택하라는 메시지가 나오면 `Weekly Total System`을 선택합니다.

가상환경 활성화 명령 없이 실행할 수 있습니다. `F5`는 디버깅 실행입니다.
보고서 전송에는 코드에 설정된 서버(`10.30.41.60:7878`)에 대한 네트워크 연결이 필요합니다.
`requirements.txt`는 GUI 실행용 의존성입니다.
