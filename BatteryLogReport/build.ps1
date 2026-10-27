$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$toolsRoot = Join-Path (Split-Path $project) 'BatteryWatch/android-app/.toolchain'
if ($env:BATTERY_REPORT_TOOLCHAIN) { $toolsRoot = $env:BATTERY_REPORT_TOOLCHAIN }
$jdk = Get-ChildItem -LiteralPath (Join-Path $toolsRoot 'java') -Directory | Select-Object -First 1
if (-not $jdk) { throw 'JDK 17 not found. Set BATTERY_REPORT_TOOLCHAIN or use Android Studio.' }
$env:JAVA_HOME = $jdk.FullName
$env:ANDROID_HOME = Join-Path $toolsRoot 'sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:GRADLE_USER_HOME = Join-Path (Split-Path $project) 'BatteryWatch/android-app/.gradle-home'
$signing = Join-Path $project 'signing'
New-Item -ItemType Directory -Path $signing -Force | Out-Null
$env:BATTERY_REPORT_KEYSTORE = Join-Path $signing 'battery-report.jks'
$passwordFile = Join-Path $signing 'password.txt'
if (-not (Test-Path -LiteralPath $env:BATTERY_REPORT_KEYSTORE)) {
    $random = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($random)
    $rng.Dispose()
    $password = [Convert]::ToBase64String($random)
    [IO.File]::WriteAllText($passwordFile, $password)
    $env:BATTERY_REPORT_STORE_PASSWORD = $password
    & (Join-Path $env:JAVA_HOME 'bin/keytool.exe') -genkeypair -keystore $env:BATTERY_REPORT_KEYSTORE -storepass:env BATTERY_REPORT_STORE_PASSWORD -keypass:env BATTERY_REPORT_STORE_PASSWORD -alias battery-report -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=Battery Log Report, O=Local Application, C=KR'
    if ($LASTEXITCODE -ne 0) { throw 'Signing key creation failed' }
} else { $env:BATTERY_REPORT_STORE_PASSWORD = [IO.File]::ReadAllText($passwordFile) }
Push-Location $project
try {
    & (Join-Path $toolsRoot 'gradle-8.11.1/bin/gradle.bat') --offline --no-daemon :app:assembleRelease
    if ($LASTEXITCODE -ne 0) { throw 'Android build failed' }
    Copy-Item -LiteralPath 'app/build/outputs/apk/release/app-release.apk' -Destination 'releases/BatteryLogReport-1.0.0.apk' -Force
    $hash = (Get-FileHash -LiteralPath 'releases/BatteryLogReport-1.0.0.apk' -Algorithm SHA256).Hash
    [IO.File]::WriteAllText((Join-Path $project 'releases/SHA256SUMS.txt'), "$hash  BatteryLogReport-1.0.0.apk`n")
} finally { Pop-Location; Remove-Item Env:BATTERY_REPORT_STORE_PASSWORD -ErrorAction SilentlyContinue }
