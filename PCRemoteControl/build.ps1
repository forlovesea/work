$ErrorActionPreference = 'Stop'
$releaseDir = "$PSScriptRoot/release/v0.1.1/win-x64"
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
dotnet publish "$PSScriptRoot/Client/PCRemoteControl.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o $releaseDir
if ($LASTEXITCODE -ne 0) { throw 'Publish failed' }
dotnet publish "$PSScriptRoot/Watchdog/PCRemoteControl.Watchdog.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o $releaseDir
if ($LASTEXITCODE -ne 0) { throw 'Watchdog publish failed' }
Copy-Item -LiteralPath "$releaseDir/PCRemoteControl.exe" -Destination "$releaseDir/PCRemoteControl-v0.1.1.exe" -Force
Copy-Item -LiteralPath "$releaseDir/PCRemoteControl.Watchdog.exe" -Destination "$releaseDir/PCRemoteControl.Watchdog-v0.1.1.exe" -Force
Copy-Item -LiteralPath "$PSScriptRoot/README.md" -Destination "$releaseDir/README.md" -Force
Set-Content -LiteralPath "$releaseDir/Start-TARGET.cmd" -Encoding ascii -Value '@start "" "%~dp0PCRemoteControl.Watchdog-v0.1.1.exe"'
Set-Content -LiteralPath "$releaseDir/Start-HOST.cmd" -Encoding ascii -Value '@start "" "%~dp0PCRemoteControl-v0.1.1.exe"'
Get-ChildItem -LiteralPath $releaseDir -File -Filter '*.exe' |
    ForEach-Object {
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        '{0}  {1}' -f $hash, $_.Name
    } |
    Set-Content -LiteralPath "$releaseDir/SHA256SUMS-v0.1.1.txt" -Encoding ascii
