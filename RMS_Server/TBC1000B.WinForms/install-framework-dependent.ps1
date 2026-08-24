param(
    [string]$InstallDirectory = (Join-Path $env:LOCALAPPDATA 'TBC1000B Monitor')
)

$ErrorActionPreference = 'Stop'
$runtimeFound = & dotnet --list-runtimes 2>$null | Where-Object { $_ -match '^Microsoft\.WindowsDesktop\.App 8\.' }
if (-not $runtimeFound) {
    throw '.NET 8 Desktop Runtime (x64)이 필요합니다: https://dotnet.microsoft.com/download/dotnet/8.0'
}

$sourceDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceExecutable = Join-Path $sourceDirectory 'TBC1000B_Monitor.exe'
if (-not (Test-Path -LiteralPath $sourceExecutable -PathType Leaf)) { throw "실행 파일이 없습니다: $sourceExecutable" }

$resolvedParent = [IO.Path]::GetFullPath((Split-Path -Parent $InstallDirectory))
$resolvedTarget = [IO.Path]::GetFullPath($InstallDirectory)
if (-not $resolvedTarget.StartsWith($resolvedParent + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw '설치 경로가 올바르지 않습니다.' }

New-Item -ItemType Directory -Path $resolvedTarget -Force | Out-Null
Copy-Item -LiteralPath $sourceExecutable -Destination $resolvedTarget -Force
$assets = Join-Path $sourceDirectory 'Assets'
if (Test-Path -LiteralPath $assets -PathType Container) { Copy-Item -LiteralPath $assets -Destination $resolvedTarget -Recurse -Force }
Write-Host "설치 완료: $resolvedTarget"
Write-Host "실행 파일: $(Join-Path $resolvedTarget 'TBC1000B_Monitor.exe')"
