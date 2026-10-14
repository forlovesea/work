@echo off
setlocal
for /d %%D in ("%~dp0*") do (
    if exist "%%~fD\server.py" (
        call "%%~fD\run.cmd" %*
        exit /b
    )
)
echo Server directory not found.
exit /b 1
