param([string]$Version = '3.2.6')
$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid version.' }
$root = $PSScriptRoot
$stage = Join-Path $root ('artifacts\single-exe-' + [Guid]::NewGuid().ToString('N'))
$output = Join-Path $stage 'publish'
$licenses = Join-Path $stage 'licenses'
$packages = (Resolve-Path (Join-Path $root '..\.nuget\packages')).Path
New-Item -ItemType Directory -Path $licenses -Force | Out-Null
Copy-Item "$packages\microsoft.netcore.app.runtime.win-x64\8.0.30\LICENSE.TXT" "$licenses\NET-LICENSE.txt"
Copy-Item "$packages\microsoft.netcore.app.runtime.win-x64\8.0.30\THIRD-PARTY-NOTICES.TXT" "$licenses\NET-THIRD-PARTY-NOTICES.txt"
Copy-Item "$packages\microsoft.windowsdesktop.app.runtime.win-x64\8.0.30\LICENSE" "$licenses\WindowsDesktop-LICENSE.txt"
& dotnet publish (Join-Path $root 'TBC1000B.WinForms.csproj') -c Release -r win-x64 --self-contained false "-p:VersionPrefix=$Version" -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=false -p:IncludeAllContentForSelfExtract=true -p:PublishTrimmed=false -p:Optimize=true -p:DebugType=None -p:DebugSymbols=false "-p:ReleaseLicenseDirectory=$licenses" "-p:RestorePackagesPath=$packages" --configfile (Join-Path $root '..\NuGet.Config') -o $output
if ($LASTEXITCODE -ne 0) { throw 'Release publish failed.' }
$exeName = "TBC1000B_Monitor_v$Version.exe"
$exe = Join-Path $output $exeName
if ((Get-Item $exe).VersionInfo.FileVersion -ne "$Version.0") { throw 'Executable version mismatch.' }
if (@(Get-ChildItem -LiteralPath $output -Recurse -File).Count -ne 1) { throw 'Publish must contain exactly one executable.' }
$final = [IO.Path]::GetFullPath((Join-Path $root 'Final'))
$archive = [IO.Path]::GetFullPath((Join-Path $stage 'previous-Final'))
if (-not $final.StartsWith($root + '\') -or -not $archive.StartsWith($root + '\')) { throw 'Path outside workspace.' }
if (Test-Path -LiteralPath $final) { Move-Item -LiteralPath $final -Destination $archive }
New-Item -ItemType Directory -Path $final | Out-Null
Copy-Item -LiteralPath $exe -Destination $final
Get-FileHash -LiteralPath (Join-Path $final $exeName) | Format-List
Get-Item -LiteralPath (Join-Path $final $exeName) | Select-Object FullName, Length
