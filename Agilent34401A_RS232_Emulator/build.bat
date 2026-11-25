@echo off
setlocal

python -m venv .venv
if errorlevel 1 exit /b 1

.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1

.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

.venv\Scripts\python.exe -m unittest test_main.py test_measurement_store.py
if errorlevel 1 exit /b 1

.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --icon assets\Agilent34401A.ico --add-data "assets\Agilent34401A.ico;assets" --name Agilent34401A_AgingReady_COMControl_AutoRecover_RoundedDisplay main.py
if errorlevel 1 exit /b 1

echo.
echo Executable created: dist\Agilent34401A_AgingReady_COMControl_AutoRecover_RoundedDisplay.exe
