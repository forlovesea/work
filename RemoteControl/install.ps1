param(
    [ValidateSet('host', 'target')][string]$Role,
    [string]$Serial,
    [string]$Adb
)
$ErrorActionPreference = 'Stop'
if (-not $Role) {
    Write-Host '1. Host - controller'
    Write-Host '2. Target - controlled device'
    $selection = Read-Host 'Select role (1/2)'
    if ($selection -eq '1') { $Role = 'host' }
    elseif ($selection -eq '2') { $Role = 'target' }
    else { throw 'Select 1 or 2.' }
}
if (-not $Adb) {
    $command = Get-Command adb -ErrorAction SilentlyContinue
    if ($command) { $Adb = $command.Source }
    elseif ($env:ANDROID_HOME -and (Test-Path "$env:ANDROID_HOME\platform-tools\adb.exe")) {
        $Adb = "$env:ANDROID_HOME\platform-tools\adb.exe"
    } else {
        $Adb = Join-Path $PSScriptRoot '..\BatteryWatch\android-app\.toolchain\sdk\platform-tools\adb.exe'
    }
}
if (-not (Test-Path -LiteralPath $Adb)) { throw 'ADB not found. Pass -Adb with the adb.exe path.' }
$apk = Join-Path $PSScriptRoot "dist\RemoteControl-$Role-debug.apk"
if (-not (Test-Path -LiteralPath $apk)) { throw 'Run build-debug.ps1 first.' }
$adbArgs = @()
if ($Serial) { $adbArgs += @('-s', $Serial) }
$adbArgs += @('install', '-r', $apk)
& $Adb @adbArgs
if ($LASTEXITCODE -ne 0) { throw 'Installation failed. Enable USB debugging; specify -Serial if multiple devices are connected.' }
Write-Host "$Role installed. Open RemoteControl $Role on the device."
