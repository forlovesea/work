@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run from BatteryWatch: py -3.10 bootstrap.py client --test
    pause
    exit /b 1
)
".venv\Scripts\python.exe" monitor.py
pause
