$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { throw 'Run setup.ps1 first.' }
& '.\.venv\Scripts\python.exe' -m pip install --no-cache-dir --disable-pip-version-check -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m PyInstaller PhotoToWord.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
Copy-Item README.md 'dist\PhotoToWord\README.md' -Force
Write-Host 'Ready: dist\PhotoToWord\PhotoToWord.exe (keep the entire folder together).'
