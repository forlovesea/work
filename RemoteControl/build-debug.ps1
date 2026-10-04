param([switch]$Offline)
$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$sharedTools = Join-Path $projectDir '..\BatteryWatch\android-app\.toolchain'
if (-not $env:JAVA_HOME -and (Test-Path "$sharedTools\java")) {
    $env:JAVA_HOME = (Get-ChildItem "$sharedTools\java" -Directory | Select-Object -First 1).FullName
}
if (-not $env:ANDROID_HOME -and (Test-Path "$sharedTools\sdk")) {
    $env:ANDROID_HOME = (Resolve-Path "$sharedTools\sdk").Path
}
$sharedCache = Join-Path $projectDir '..\BatteryWatch\android-app\.gradle-home'
if (-not $env:GRADLE_USER_HOME -and (Test-Path $sharedCache)) {
    $env:GRADLE_USER_HOME = (Resolve-Path $sharedCache).Path
}
if (-not $env:JAVA_HOME) { throw 'Set JAVA_HOME to JDK 17 before building.' }
Push-Location $projectDir
try {
    $buildArgs = @('--no-daemon', ':app:assembleHostDebug', ':app:assembleTargetDebug',
        ':app:testHostDebugUnitTest', ':app:testTargetDebugUnitTest', ':app:lintHostDebug', ':app:lintTargetDebug')
    if ($Offline) { $buildArgs = @('--offline') + $buildArgs }
    & .\gradlew.bat @buildArgs
    if ($LASTEXITCODE -ne 0) { throw 'Build or checks failed.' }
    New-Item -ItemType Directory -Force dist | Out-Null
    foreach ($role in @('host', 'target')) {
        Copy-Item "app\build\outputs\apk\$role\debug\app-$role-debug.apk" "dist\RemoteControl-$role-debug.apk" -Force
    }
    Get-ChildItem dist\*.apk | ForEach-Object {
        '{0}  {1}' -f (Get-FileHash -Algorithm SHA256 $_.FullName).Hash, $_.Name
    } | Set-Content -Encoding ascii dist\SHA256SUMS.txt
    Write-Output 'Debug APKs and checksums are in dist/.'
} finally { Pop-Location }
