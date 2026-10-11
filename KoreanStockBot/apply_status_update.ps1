$ErrorActionPreference = 'Stop'
$destination = $PSScriptRoot
$source = Join-Path $destination 'MarketStatusUpdate\KoreanStockBot'
if (-not (Test-Path -LiteralPath (Join-Path $source 'KoreanStockBotETF.exe'))) {
    throw 'Update files not found.'
}
$running = Get-Process -Name KoreanStockBotETF,KoreanStockBotStock,KoreanStockBotPaper,trader,research -ErrorAction SilentlyContinue
if ($running) {
    throw 'Stop trading from the GUI and close all KoreanStockBot windows before applying the update. No process was terminated.'
}
# Preserve runtime, research, credentials, STOP and both user's config files.
foreach ($name in @('KoreanStockBotETF.exe','KoreanStockBotStock.exe','KoreanStockBotPaper.exe','trader.exe','research.exe','_internal','GUI_GUIDE.md')) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination $destination -Recurse -Force
}
Get-ChildItem -LiteralPath $source -Filter '*.docx' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
}
Write-Output 'Update complete. Existing settings and trading records were preserved.'
