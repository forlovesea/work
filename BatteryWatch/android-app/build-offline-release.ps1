$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$javaRoot = Join-Path $projectRoot '.toolchain\java'
$java = if (Test-Path -LiteralPath $javaRoot -PathType Container) {
    Get-ChildItem -LiteralPath $javaRoot -Directory | Select-Object -First 1
}
$sdk = Join-Path $projectRoot '.toolchain\sdk'

if (-not $java) {
    throw "JDK 17 was not found under $javaRoot."
}
if (-not (Test-Path -LiteralPath $sdk -PathType Container)) {
    throw "Android SDK was not found under $sdk."
}

$storeFile = (Read-Host 'Customer keystore file path').Trim('"')
if (-not (Test-Path -LiteralPath $storeFile -PathType Leaf)) {
    throw 'The specified customer keystore file does not exist.'
}
$storeFile = [System.IO.Path]::GetFullPath($storeFile)
$keyAlias = Read-Host 'Keystore key alias'
$storePasswordSecure = Read-Host 'Keystore password' -AsSecureString
$keyPasswordSecure = Read-Host 'Key password' -AsSecureString

function ConvertTo-PlainText([System.Security.SecureString] $Secret) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

Push-Location $projectRoot
try {
    $env:JAVA_HOME = $java.FullName
    $env:ANDROID_HOME = $sdk
    $env:ANDROID_SDK_ROOT = $sdk
    $env:PATH = (Join-Path $java.FullName 'bin') + ';' + $env:PATH
    $env:BW_ANDROID_STORE_FILE = $storeFile
    $env:BW_ANDROID_STORE_PASSWORD = ConvertTo-PlainText $storePasswordSecure
    $env:BW_ANDROID_KEY_ALIAS = $keyAlias
    $env:BW_ANDROID_KEY_PASSWORD = ConvertTo-PlainText $keyPasswordSecure

    & (Join-Path $projectRoot 'gradlew.bat') --no-daemon :app:assembleOfflineRelease
    if ($LASTEXITCODE -ne 0) {
        throw "Gradle release build failed with exit code $LASTEXITCODE."
    }

    $apk = Join-Path $projectRoot 'app\build\outputs\apk\offline\release\app-offline-release.apk'
    if (-not (Test-Path -LiteralPath $apk -PathType Leaf)) {
        throw 'Gradle succeeded but the offline Release APK was not produced.'
    }

    $package = Join-Path $projectRoot '..\dist\customer-release\android-app'
    if (-not (Test-Path -LiteralPath $package -PathType Container)) {
        throw "Android customer package directory does not exist: $package"
    }
    $apkName = 'BatteryWatch_Android_offline_Release.apk'
    $packageApk = Join-Path $package $apkName
    Copy-Item -LiteralPath $apk -Destination $packageApk -Force
    $apkHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $packageApk).Hash
    Set-Content -LiteralPath (Join-Path $package 'SHA256SUMS.txt') -Value "$apkHash  $apkName" -Encoding ascii
    $status = @"
READY FOR CUSTOMER DELIVERY

Offline Release APK: $apkName
SHA-256: $apkHash
Firebase push is not included.
"@
    Set-Content -LiteralPath (Join-Path $package 'PACKAGE_STATUS.txt') -Value $status -Encoding utf8

    $deliveryRoot = Split-Path -Parent $package
    $zipPath = Join-Path $deliveryRoot 'BatteryWatch_Android_offline_Release.zip'
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $package,
        $zipPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $true
    )
    $zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash
    $sumFile = Join-Path $deliveryRoot 'SHA256SUMS.txt'
    $existingSums = Get-Content -LiteralPath $sumFile | Where-Object {
        $_ -notmatch 'android-app/BatteryWatch_Android_offline_Release\.apk|BatteryWatch_Android_offline_Release\.zip'
    }
    Set-Content -LiteralPath $sumFile -Value $existingSums -Encoding ascii
    Add-Content -LiteralPath $sumFile -Value "$apkHash  android-app/$apkName" -Encoding ascii
    Add-Content -LiteralPath $sumFile -Value "$zipHash  BatteryWatch_Android_offline_Release.zip" -Encoding ascii

    Write-Output "Signed APK copied to: $packageApk"
    Write-Output "Android delivery ZIP: $zipPath"
}
finally {
    Remove-Item Env:BW_ANDROID_STORE_FILE, Env:BW_ANDROID_STORE_PASSWORD, Env:BW_ANDROID_KEY_ALIAS, Env:BW_ANDROID_KEY_PASSWORD -ErrorAction SilentlyContinue
    Pop-Location
}
