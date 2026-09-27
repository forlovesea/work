$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 or later is required.' }
& '.\.venv\Scripts\python.exe' -m pip install --no-cache-dir --disable-pip-version-check 'pip==26.0.1'
if ($LASTEXITCODE -ne 0) { throw 'pip installation failed.' }
& '.\.venv\Scripts\python.exe' -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Python setup complete. See README.md for Tesseract + Korean language setup.'
