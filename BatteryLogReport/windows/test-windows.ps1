$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot
$package = Join-Path $project 'releases/BatteryLogReport-Windows-x64'
$exe = Join-Path $package 'BatteryLogReport.exe'
function Assert-X64([string]$path) {
    $bytes = [IO.File]::ReadAllBytes($path)
    $pe = [BitConverter]::ToInt32($bytes, 0x3c)
    if ([BitConverter]::ToUInt16($bytes, $pe + 4) -ne 0x8664) { throw "Not x64: $path" }
    if ([BitConverter]::ToUInt16($bytes, $pe + 24) -ne 0x20b) { throw "Not PE32+: $path" }
    $major = [BitConverter]::ToUInt16($bytes, $pe + 24 + 48)
    $minor = [BitConverter]::ToUInt16($bytes, $pe + 24 + 50)
    if ($major -gt 6 -or ($major -eq 6 -and $minor -gt 1)) { throw "Subsystem version exceeds Windows 7: $path" }
    Write-Output ("PE x64 / subsystem {0}.{1}: {2}" -f $major,$minor,[IO.Path]::GetFileName($path))
}
Assert-X64 $exe
Assert-X64 (Join-Path $package 'runtime/bin/javaw.exe')
Assert-X64 (Join-Path $package 'runtime/bin/server/jvm.dll')
$test = Start-Process -FilePath $exe -ArgumentList @('--self-test',('"' + $project + '"')) -WindowStyle Hidden -Wait -PassThru
if ($test.ExitCode -ne 0) { Get-Content -LiteralPath (Join-Path $project 'qa/windows-test-results.txt') -Encoding UTF8 -ErrorAction SilentlyContinue; throw 'Native x64 package self-test failed.' }
Get-Content -LiteralPath (Join-Path $project 'qa/windows-test-results.txt') -Encoding UTF8
$workspace = Split-Path $project
$jdk = Get-ChildItem -LiteralPath (Join-Path $workspace 'BatteryWatch/android-app/.toolchain/java') -Directory | Select-Object -First 1
$tests = Join-Path $PSScriptRoot 'build/tests'
New-Item -ItemType Directory -Path $tests -Force | Out-Null
& (Join-Path $jdk.FullName 'bin/javac.exe') --release 8 -encoding UTF-8 -cp (Join-Path $package 'BatteryLogReport.jar') -d $tests (Join-Path $project 'tools/Regression.java')
if ($LASTEXITCODE -ne 0) { throw 'Java 8 regression compilation failed.' }
& (Join-Path $package 'runtime/bin/java.exe') '-Djava.awt.headless=true' -cp ($tests + ';' + (Join-Path $package 'BatteryLogReport.jar')) kr.co.batteryreport.Regression $project
if ($LASTEXITCODE -ne 0) { throw 'Java 8 regression failed.' }
$render = Start-Process -FilePath $exe -ArgumentList @('--render-ui',('"' + $project + '"')) -WindowStyle Hidden -Wait -PassThru
if ($render.ExitCode -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $project 'qa/windows-ui.png'))) { throw 'Windows UI render failed.' }
Write-Output 'PASS: packaged EXE / bundled x64 Java 8 / shared regression / Windows UI render.'
