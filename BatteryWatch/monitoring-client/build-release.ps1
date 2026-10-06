param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & $Python -c "import sys; assert sys.version_info[:2] == (3, 10), 'Use Python 3.10 for the SNMP stack'"
    if ($LASTEXITCODE -ne 0) { throw 'Python version check failed' }
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    & $Python -m PyInstaller --noconfirm --clean --distpath dist --workpath build BatteryWatch-Monitor.spec
    if ($LASTEXITCODE -ne 0) { throw 'Packaging failed' }
    $releaseExe = Join-Path $PSScriptRoot 'dist/BatteryWatch-Monitor.exe'
    $report = Join-Path $PSScriptRoot 'build/frozen-self-test.json'
    $process = Start-Process -FilePath $releaseExe -ArgumentList @('--self-test', ('"' + $report + '"')) -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(120000)) { $process.Kill(); throw 'Packaged smoke test timed out' }
    $process.Refresh()
    if ($process.ExitCode -ne 0 -or -not (Test-Path $report)) { throw 'Packaged smoke test failed; inspect build/frozen-self-test.json' }
    $check = Get-Content -Raw -Encoding UTF8 $report | ConvertFrom-Json
    if (-not $check.ok) { throw $check.error }
    $hash = (Get-FileHash -Algorithm SHA256 $releaseExe).Hash
    "$hash  BatteryWatch-Monitor.exe" | Set-Content -Encoding ascii dist/SHA256SUMS.txt
    Write-Output 'Verified single executable: dist/BatteryWatch-Monitor.exe'
} finally { Pop-Location }
