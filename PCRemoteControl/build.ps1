param([switch]$IncludeWatchdog)
$ErrorActionPreference = 'Stop'
$version = '0.2.2'
$clientExeName = "PCRemoteControl-v$version.exe"
$releaseDir = Join-Path $PSScriptRoot "release/v$version"
$publishDir = Join-Path $PSScriptRoot "Client/obj/publish-v$version"
$ffmpegVersion = '8.1'
$ffmpegRoot = Join-Path $PSScriptRoot "Client/obj/ffmpeg-n$ffmpegVersion-win64-lgpl-shared"
$ffmpegArchive = Join-Path $ffmpegRoot "ffmpeg-n$ffmpegVersion-win64-lgpl-shared.zip"
$ffmpegExtractDir = Join-Path $ffmpegRoot 'extracted'
$ffmpegUrl = 'https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-win64-lgpl-shared-8.1.zip'
$ffmpegSha256 = 'b96be85e024a68514876582e19a80062152cc499cb38efd70e9db72f7108d9c5'
$gplLicenseUrl = 'https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1/COPYING.GPLv3'
$gplLicenseSha256 = '8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903'
$gplLicensePath = Join-Path $ffmpegRoot 'COPYING.GPLv3'
$requiredFfmpegLibraries = @(
    'avcodec-62.dll',
    'avdevice-62.dll',
    'avfilter-11.dll',
    'avformat-62.dll',
    'avutil-60.dll',
    'swresample-6.dll',
    'swscale-9.dll'
)

New-Item -ItemType Directory -Path $ffmpegRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $ffmpegArchive)) {
    $downloadPath = "$ffmpegArchive.download"
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $ffmpegUrl -OutFile $downloadPath
        $downloadSha256 = (Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($downloadSha256 -ne $ffmpegSha256) {
            throw "FFmpeg archive checksum mismatch. Expected $ffmpegSha256, got $downloadSha256."
        }
        Move-Item -LiteralPath $downloadPath -Destination $ffmpegArchive
    }
    finally {
        if (Test-Path -LiteralPath $downloadPath) {
            Remove-Item -LiteralPath $downloadPath -Force
        }
    }
}
$actualFfmpegSha256 = (Get-FileHash -LiteralPath $ffmpegArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualFfmpegSha256 -ne $ffmpegSha256) {
    throw "FFmpeg archive checksum mismatch. Expected $ffmpegSha256, got $actualFfmpegSha256."
}
if (-not (Test-Path -LiteralPath $gplLicensePath)) {
    $downloadPath = "$gplLicensePath.download"
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $gplLicenseUrl -OutFile $downloadPath
        $downloadSha256 = (Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($downloadSha256 -ne $gplLicenseSha256) {
            throw "GPL license checksum mismatch. Expected $gplLicenseSha256, got $downloadSha256."
        }
        Move-Item -LiteralPath $downloadPath -Destination $gplLicensePath
    }
    finally {
        if (Test-Path -LiteralPath $downloadPath) {
            Remove-Item -LiteralPath $downloadPath -Force
        }
    }
}
$actualGplLicenseSha256 = (Get-FileHash -LiteralPath $gplLicensePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualGplLicenseSha256 -ne $gplLicenseSha256) {
    throw "GPL license checksum mismatch. Expected $gplLicenseSha256, got $actualGplLicenseSha256."
}

$ffmpegBin = Get-ChildItem -LiteralPath $ffmpegExtractDir -Directory -Recurse -ErrorAction SilentlyContinue |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'avcodec-62.dll') } |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $ffmpegBin) {
    Expand-Archive -LiteralPath $ffmpegArchive -DestinationPath $ffmpegExtractDir -Force
    $ffmpegBin = Get-ChildItem -LiteralPath $ffmpegExtractDir -Directory -Recurse |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'avcodec-62.dll') } |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $ffmpegBin) {
    throw 'The downloaded FFmpeg archive does not contain the expected Windows x64 shared libraries.'
}
foreach ($library in $requiredFfmpegLibraries) {
    if (-not (Test-Path -LiteralPath (Join-Path $ffmpegBin $library))) {
        throw "Required FFmpeg library is missing: $library"
    }
}
$ffmpegLicense = Get-ChildItem -LiteralPath $ffmpegExtractDir -Filter 'LICENSE.txt' -File -Recurse |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $ffmpegLicense) {
    throw 'The FFmpeg archive does not contain its LGPL license text.'
}

New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
dotnet publish "$PSScriptRoot/Client/PCRemoteControl.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true "-p:FFmpegNativeDir=$ffmpegBin" -p:NuGetAudit=false -o $publishDir
if ($LASTEXITCODE -ne 0) { throw 'Client publish failed' }
Copy-Item -LiteralPath "$publishDir/PCRemoteControl.exe" -Destination (Join-Path $releaseDir $clientExeName) -Force
Copy-Item -LiteralPath $ffmpegLicense -Destination "$releaseDir/FFmpeg-LICENSE.txt" -Force
Copy-Item -LiteralPath $gplLicensePath -Destination "$releaseDir/GPL-LICENSE.txt" -Force
@"
PCRemoteControl includes FFmpeg 8.1 LGPL Shared Windows x64 libraries.
FFmpeg source: https://github.com/FFmpeg/FFmpeg/tree/n8.1
Build scripts and Windows binaries: https://github.com/FFmpeg-Builds/FFmpeg-Builds
Binary package SHA-256: $ffmpegSha256
"@ | Set-Content -LiteralPath (Join-Path $releaseDir 'FFmpeg-NOTICE.txt') -Encoding ascii
if ($IncludeWatchdog) {
    $watchdogPublishDir = Join-Path $PSScriptRoot "Watchdog/obj/publish-v$version"
    dotnet publish "$PSScriptRoot/Watchdog/PCRemoteControl.Watchdog.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:NuGetAudit=false -o $watchdogPublishDir
    if ($LASTEXITCODE -ne 0) { throw 'Watchdog publish failed' }
    Copy-Item -LiteralPath "$watchdogPublishDir/PCRemoteControl.Watchdog.exe" -Destination "$releaseDir/PCRemoteControl.Watchdog-v$version.exe" -Force
}
$releaseExecutables = @((Join-Path $releaseDir $clientExeName))
if ($IncludeWatchdog) {
    $releaseExecutables += Join-Path $releaseDir "PCRemoteControl.Watchdog-v$version.exe"
}
$releaseExecutables |
    ForEach-Object {
        $hash = (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()
        '{0}  {1}' -f $hash, [IO.Path]::GetFileName($_)
    } |
    Set-Content -LiteralPath "$releaseDir/SHA256SUMS-v$version.txt" -Encoding ascii
