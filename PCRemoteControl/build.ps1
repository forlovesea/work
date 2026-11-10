param([switch]$IncludeWatchdog)
$ErrorActionPreference = 'Stop'
$version = '0.1.3'
$releaseDir = Join-Path $PSScriptRoot "release/v$version"
$publishDir = Join-Path $PSScriptRoot "Client/obj/publish-v$version"
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
dotnet publish "$PSScriptRoot/Client/PCRemoteControl.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:NuGetAudit=false -o $publishDir
if ($LASTEXITCODE -ne 0) { throw 'Client publish failed' }
Copy-Item -LiteralPath "$publishDir/PCRemoteControl.exe" -Destination "$releaseDir/PCRemoteControl-v$version.exe" -Force
if ($IncludeWatchdog) {
    $watchdogPublishDir = Join-Path $PSScriptRoot "Watchdog/obj/publish-v$version"
    dotnet publish "$PSScriptRoot/Watchdog/PCRemoteControl.Watchdog.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:NuGetAudit=false -o $watchdogPublishDir
    if ($LASTEXITCODE -ne 0) { throw 'Watchdog publish failed' }
    Copy-Item -LiteralPath "$watchdogPublishDir/PCRemoteControl.Watchdog.exe" -Destination "$releaseDir/PCRemoteControl.Watchdog-v$version.exe" -Force
}
Get-ChildItem -LiteralPath $releaseDir -File -Filter '*.exe' |
    ForEach-Object {
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        '{0}  {1}' -f $hash, $_.Name
    } |
    Set-Content -LiteralPath "$releaseDir/SHA256SUMS-v$version.txt" -Encoding ascii
