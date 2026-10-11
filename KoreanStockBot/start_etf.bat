@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install_auto.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -X utf8 app.py --mode etf
pause
