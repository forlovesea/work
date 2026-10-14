@echo off
setlocal
set "MEETING_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%MEETING_PYTHON%" set "MEETING_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%MEETING_PYTHON%" (
    echo Create .venv with Python 3.12 and install requirements.txt first.
    exit /b 1
)
"%MEETING_PYTHON%" "%~dp0server.py" %*
exit /b %errorlevel%
