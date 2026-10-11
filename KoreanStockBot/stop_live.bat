@echo off
cd /d "%~dp0"
type nul > STOP
echo Stop requested. The bot will cancel its pending order and wait for confirmation.
echo Existing holdings are retained. Check remaining orders in Toss if the bot is offline.
pause
