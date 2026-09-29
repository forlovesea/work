@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run from BatteryWatch: py -3.12 bootstrap.py server --test
    pause
    exit /b 1
)
".venv\Scripts\python.exe" server.py run
pause
