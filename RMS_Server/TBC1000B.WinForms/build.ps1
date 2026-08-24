$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:DOTNET_CLI_HOME = $workspaceRoot
$env:APPDATA = Join-Path $workspaceRoot '.appdata'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$env:DOTNET_NOLOGO = '1'
New-Item -ItemType Directory -Path $env:APPDATA -Force | Out-Null

$localDotnet = Join-Path $workspaceRoot '.dotnet\dotnet.exe'
$taskDotnet = if (Test-Path -LiteralPath $localDotnet -PathType Leaf) { $localDotnet } else { (Get-Command dotnet -ErrorAction Stop).Source }

& $taskDotnet build (Join-Path $PSScriptRoot 'TBC1000B.WinForms.csproj') --configuration Debug --configfile (Join-Path $workspaceRoot 'NuGet.Config')
