$ErrorActionPreference = 'Stop'

$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$javaRoot = Join-Path $projectRoot '.toolchain\java'
$java = if (Test-Path -LiteralPath $javaRoot -PathType Container) {
    Get-ChildItem -LiteralPath $javaRoot -Directory | Select-Object -First 1
}

if (-not $java) {
    throw "JDK 17 was not found under $javaRoot."
}
$keytool = Join-Path $java.FullName 'bin\keytool.exe'
if (-not (Test-Path -LiteralPath $keytool -PathType Leaf)) {
    throw "keytool.exe was not found under $($java.FullName)."
}

$defaultDirectory = Join-Path $env:USERPROFILE 'BatteryWatchSigning'
$defaultFile = Join-Path $defaultDirectory 'BatteryWatch-Android-Release.jks'
$enteredPath = Read-Host "New keystore file path [$defaultFile]"
$storeFile = if ([string]::IsNullOrWhiteSpace($enteredPath)) { $defaultFile } else { $enteredPath.Trim('"') }
$storeFile = [System.IO.Path]::GetFullPath($storeFile)

if ($storeFile.StartsWith($projectRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Store the signing keystore outside the BatteryWatch source checkout.'
}
if (Test-Path -LiteralPath $storeFile) {
    throw "A file already exists at $storeFile. Choose a new path; existing signing keys are never overwritten."
}

$alias = Read-Host 'Key alias [batterywatch-release]'
if ([string]::IsNullOrWhiteSpace($alias)) {
    $alias = 'batterywatch-release'
}
$commonName = Read-Host 'Certificate common name [BatteryWatch Android Release]'
if ([string]::IsNullOrWhiteSpace($commonName)) {
    $commonName = 'BatteryWatch Android Release'
}
if ($commonName -match '[,+=<>#;"]') {
    throw 'Use a common name without commas or distinguished-name punctuation.'
}

$storePasswordSecure = Read-Host 'New keystore password (minimum 6 characters)' -AsSecureString
$confirmPasswordSecure = Read-Host 'Confirm keystore password' -AsSecureString

function ConvertTo-PlainText([System.Security.SecureString] $Secret) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

$storePassword = ConvertTo-PlainText $storePasswordSecure
$confirmPassword = ConvertTo-PlainText $confirmPasswordSecure
if ($storePassword.Length -lt 6) {
    throw 'The keystore password must contain at least 6 characters.'
}
if ($storePassword -cne $confirmPassword) {
    throw 'The entered passwords do not match.'
}
Remove-Variable confirmPassword, confirmPasswordSecure, storePasswordSecure

$parent = Split-Path -Parent $storeFile
New-Item -ItemType Directory -Path $parent -Force | Out-Null

try {
    $env:BW_ANDROID_KEYSTORE_PASSWORD = $storePassword
    $arguments = @(
        '-genkeypair',
        '-alias', $alias,
        '-keyalg', 'RSA',
        '-keysize', '3072',
        '-validity', '10000',
        '-storetype', 'JKS',
        '-keystore', $storeFile,
        '-dname', "CN=$commonName",
        '-storepass:env', 'BW_ANDROID_KEYSTORE_PASSWORD',
        '-keypass:env', 'BW_ANDROID_KEYSTORE_PASSWORD'
    )
    & $keytool @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "keytool failed with exit code $LASTEXITCODE."
    }
    if (-not (Test-Path -LiteralPath $storeFile -PathType Leaf)) {
        throw 'keytool reported success but the keystore file was not created.'
    }

    Write-Output "Customer signing keystore created: $storeFile"
    Write-Output "Key alias: $alias"
    Write-Warning 'Keep this keystore and its password in a secure backup. The same key is required for every future app update.'
    Write-Warning 'Do not upload the keystore or share its password. The password will be requested again by build-offline-release.ps1.'
}
finally {
    Remove-Item Env:BW_ANDROID_KEYSTORE_PASSWORD -ErrorAction SilentlyContinue
    Remove-Variable storePassword -ErrorAction SilentlyContinue
}
