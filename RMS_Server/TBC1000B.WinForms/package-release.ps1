param([string]$Version = '3.2.6')

$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$workspaceRoot = (Resolve-Path (Join-Path $projectDirectory '..')).Path
$localDotnet = Join-Path $workspaceRoot '.dotnet\dotnet.exe'
$dotnet = if (Test-Path -LiteralPath $localDotnet -PathType Leaf) { $localDotnet } else { (Get-Command dotnet -ErrorAction Stop).Source }
$project = Join-Path $projectDirectory 'TBC1000B.WinForms.csproj'
$releaseDirectory = Join-Path $projectDirectory 'release-packages'
$frameworkOutput = Join-Path $projectDirectory 'publish\framework-dependent'
$selfContainedOutput = Join-Path $projectDirectory 'publish\self-contained'

$env:DOTNET_CLI_HOME = $workspaceRoot
$env:APPDATA = Join-Path $workspaceRoot '.appdata'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$env:DOTNET_NOLOGO = '1'

New-Item -ItemType Directory -Path $releaseDirectory -Force | Out-Null

& $dotnet publish $project -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:DebugType=None -p:DebugSymbols=false -o $frameworkOutput --no-restore
if ($LASTEXITCODE -ne 0) { throw 'Framework-dependent publish 실패' }
Copy-Item -LiteralPath (Join-Path $projectDirectory 'install-framework-dependent.ps1') -Destination $frameworkOutput -Force

& $dotnet publish $project -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:PublishTrimmed=false -p:DebugType=None -p:DebugSymbols=false -o $selfContainedOutput --no-restore
if ($LASTEXITCODE -ne 0) { throw 'Self-contained publish 실패' }

$frameworkZip = Join-Path $releaseDirectory "TBC1000B-Monitor-$Version-framework-dependent.zip"
$selfContainedZip = Join-Path $releaseDirectory "TBC1000B-Monitor-$Version-self-contained.zip"
if (Test-Path -LiteralPath $frameworkZip) { Remove-Item -LiteralPath $frameworkZip -Force }
if (Test-Path -LiteralPath $selfContainedZip) { Remove-Item -LiteralPath $selfContainedZip -Force }
Compress-Archive -Path (Join-Path $frameworkOutput '*') -DestinationPath $frameworkZip -CompressionLevel Optimal
Compress-Archive -Path (Join-Path $selfContainedOutput '*') -DestinationPath $selfContainedZip -CompressionLevel Optimal

Get-Item -LiteralPath $frameworkZip, $selfContainedZip | Select-Object FullName, @{Name='SizeMiB';Expression={[Math]::Round($_.Length / 1MB, 2)}}
