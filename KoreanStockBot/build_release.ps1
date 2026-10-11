param([string]$DistPath = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$releaseVersion = & .\.venv\Scripts\python.exe prepare_version.py
if ($LASTEXITCODE -ne 0) { throw 'Version preparation failed' }
if (-not $DistPath) { $DistPath = "Release\v$releaseVersion" }
$releaseTarget = Join-Path (Join-Path $PSScriptRoot $DistPath) 'KoreanStockBot'
foreach ($personalDirectory in @('runtime','research')) {
    if (Test-Path -LiteralPath (Join-Path $releaseTarget $personalDirectory)) {
        throw 'Existing release has runtime/research data. Build in a fresh checkout; do not overwrite trading records.'
    }
}
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --distpath $DistPath --workpath build\release KoreanStockBot.spec
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
foreach ($configName in @('etf_config.json', 'live_config.json')) {
    $configTarget = Join-Path $releaseTarget $configName
    if (-not (Test-Path -LiteralPath $configTarget)) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $configName) -Destination $configTarget
    }
}
foreach ($docName in @('GUI_GUIDE.md','EXE_BUILD_GUIDE.md','RELEASE_README.txt','CHANGELOG.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $docName) -Destination $releaseTarget
}
Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.docx' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $releaseTarget
}
Write-Output "Release ready: $releaseTarget"
