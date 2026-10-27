$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$dest = Join-Path $PSScriptRoot 'tools'
$metadataPath = Join-Path $dest 'liberica-x64-metadata.json'
if (-not (Test-Path -LiteralPath $metadataPath)) { Invoke-WebRequest -UseBasicParsing -Uri 'https://api.bell-sw.com/v1/liberica/releases?version-feature=8&os=windows&arch=x86&bitness=64&package-type=zip' -OutFile $metadataPath }
$metadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
$runtime = $metadata | Where-Object { $_.bundleType -eq 'jre' -and $_.GA } | Sort-Object updateVersion,buildVersion -Descending | Select-Object -First 1
if (-not $runtime -or $runtime.bitness -ne 64) { throw 'No matching Windows x64 Java 8 runtime found.' }
$runtime | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $dest 'runtime-x64-selected.json') -Encoding UTF8
$archive = Join-Path $dest $runtime.filename
if (-not (Test-Path -LiteralPath $archive)) { Invoke-WebRequest -UseBasicParsing -Uri $runtime.downloadUrl -OutFile $archive }
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA1).Hash.ToLowerInvariant() -ne $runtime.sha1) { throw 'Runtime checksum mismatch.' }
$runtimeDir = Join-Path $dest 'runtime-x64-unpacked'
if (-not (Test-Path -LiteralPath $runtimeDir)) { Expand-Archive -LiteralPath $archive -DestinationPath $runtimeDir }
$indexPath = Join-Path $dest 'zig-index.json'
if (-not (Test-Path -LiteralPath $indexPath)) { Invoke-WebRequest -UseBasicParsing -Uri 'https://ziglang.org/download/index.json' -OutFile $indexPath }
$zig = (Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json).'0.13.0'.'x86_64-windows'
$compilerArchive = Join-Path $dest 'zig-windows-x86_64-0.13.0.zip'
if (-not (Test-Path -LiteralPath $compilerArchive)) { Invoke-WebRequest -UseBasicParsing -Uri $zig.tarball -OutFile $compilerArchive }
if ((Get-FileHash -LiteralPath $compilerArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $zig.shasum) { throw 'Compiler checksum mismatch.' }
$compilerDir = Join-Path $dest 'zig-unpacked'
if (-not (Test-Path -LiteralPath $compilerDir)) { Expand-Archive -LiteralPath $compilerArchive -DestinationPath $compilerDir }
Write-Output ('Downloaded and verified Liberica ' + $runtime.version + ' x64 JRE and Zig 0.13.0 compiler.')
