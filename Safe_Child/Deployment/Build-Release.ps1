param([switch]$PackageOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$releaseRoot = Join-Path $projectRoot 'Final\_Release'
$appRoot = Join-Path $releaseRoot 'App'
Push-Location $projectRoot
try {
    if (-not $PackageOnly) {
        dotnet publish SafeChild.csproj -p:PublishProfile=Windows10-x64
        if ($LASTEXITCODE -ne 0) { throw 'Publish failed.' }
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Install.cmd'), (Join-Path $PSScriptRoot 'Install.ps1'), (Join-Path $PSScriptRoot 'README-ko.md') -Destination $releaseRoot -Force
    if (-not $PackageOnly) { Compress-Archive -Path (Join-Path $appRoot '*') -DestinationPath (Join-Path $releaseRoot 'Payload.zip') -CompressionLevel Optimal -Force }
    $setupPath = Join-Path $releaseRoot 'SafeChild-Setup-Win10-x64.exe'
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    & $compiler /nologo /target:winexe /platform:x64 /optimize+ /codepage:65001 "/out:$setupPath" `
        "/win32manifest:$projectRoot\app.manifest" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll `
        "/resource:$releaseRoot\Payload.zip,Payload.zip" "/resource:$releaseRoot\Install.ps1,Install.ps1" `
        (Join-Path $PSScriptRoot 'Setup.cs')
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $setupPath)) { throw 'Setup executable packaging failed.' }
    Get-ChildItem -LiteralPath $releaseRoot -File | Where-Object Name -ne 'SHA256SUMS.txt' |
        Get-FileHash -Algorithm SHA256 | ForEach-Object { $_.Hash + '  ' + (Split-Path $_.Path -Leaf) } |
        Set-Content -LiteralPath (Join-Path $releaseRoot 'SHA256SUMS.txt') -Encoding ASCII
}
finally { Pop-Location }
