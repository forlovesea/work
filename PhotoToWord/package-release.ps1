param(
    [string]$Version = '1.0.0',
    [string]$TesseractDirectory = 'C:\Program Files\Tesseract-OCR'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($Version -notmatch '^\d+\.\d+\.\d+([.-][A-Za-z0-9]+)*$') { throw 'Invalid version.' }
if (-not (Test-Path -LiteralPath 'dist\PhotoToWord\PhotoToWord.exe')) { throw 'Run build.ps1 first.' }
foreach ($file in @('tesseract.exe', 'doc\LICENSE', 'tessdata\kor.traineddata', 'tessdata\eng.traineddata')) {
    if (-not (Test-Path -LiteralPath (Join-Path $TesseractDirectory $file))) { throw "Missing OCR runtime file: $file" }
}
$packageRoot = Join-Path $PSScriptRoot "release\PhotoToWord-$Version-windows-x64"
if (Test-Path -LiteralPath $packageRoot) { throw "Package already exists: $packageRoot. Choose a new version or archive the existing package." }
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
Copy-Item -LiteralPath 'dist\PhotoToWord' -Destination $packageRoot -Recurse
$appRoot = Join-Path $packageRoot 'PhotoToWord'
$ocrRoot = Join-Path $appRoot 'tools\Tesseract-OCR'
New-Item -ItemType Directory -Path (Join-Path $ocrRoot 'tessdata') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $TesseractDirectory 'tesseract.exe') -Destination $ocrRoot
Get-ChildItem -LiteralPath $TesseractDirectory -Filter '*.dll' -File | Copy-Item -Destination $ocrRoot
Copy-Item -LiteralPath (Join-Path $TesseractDirectory 'doc') -Destination $ocrRoot -Recurse
foreach ($name in @('kor.traineddata', 'eng.traineddata', 'osd.traineddata', 'configs', 'tessconfigs', 'pdf.ttf')) {
    $source = Join-Path $TesseractDirectory "tessdata\$name"
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $ocrRoot 'tessdata') -Recurse }
}
Copy-Item -LiteralPath 'README.md', 'THIRD_PARTY_NOTICES.md' -Destination $appRoot
Copy-Item -LiteralPath 'RELEASE_README.md' -Destination (Join-Path $packageRoot 'START_HERE.md')
Copy-Item -LiteralPath 'samples\sample.png', 'samples\korean_ocr_verified\korean_sample.png' -Destination $appRoot
& '.\.venv\Scripts\python.exe' collect-licenses.py (Join-Path $appRoot 'licenses')
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
$launcher = "@echo off`r`ncd /d `"%~dp0PhotoToWord`"`r`nstart `"`" `"PhotoToWord.exe`"`r`n"
[System.IO.File]::WriteAllText((Join-Path $packageRoot 'START.bat'), $launcher, [System.Text.Encoding]::ASCII)
& (Join-Path $ocrRoot 'tesseract.exe') --list-langs
if ($LASTEXITCODE -ne 0) { throw 'Bundled OCR runtime failed.' }
$archive = "$packageRoot.zip"
Compress-Archive -LiteralPath $packageRoot -DestinationPath $archive -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText("$archive.sha256", "$hash  $([System.IO.Path]::GetFileName($archive))`n", [System.Text.Encoding]::ASCII)
Write-Host "Ready: $archive"
