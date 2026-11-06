$ErrorActionPreference = 'Stop'
dotnet publish "$PSScriptRoot/Client/PCRemoteControl.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o "$PSScriptRoot/release/win-x64"
if ($LASTEXITCODE -ne 0) { throw 'Publish failed' }
dotnet publish "$PSScriptRoot/Watchdog/PCRemoteControl.Watchdog.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o "$PSScriptRoot/release/win-x64"
if ($LASTEXITCODE -ne 0) { throw 'Watchdog publish failed' }
Copy-Item -LiteralPath "$PSScriptRoot/README.md" -Destination "$PSScriptRoot/release/win-x64/README.md"
Set-Content -LiteralPath "$PSScriptRoot/release/win-x64/Start-TARGET.cmd" -Encoding ascii -Value '@start "" "%~dp0PCRemoteControl.Watchdog.exe"'
Set-Content -LiteralPath "$PSScriptRoot/release/win-x64/Start-HOST.cmd" -Encoding ascii -Value '@start "" "%~dp0PCRemoteControl.exe"'
