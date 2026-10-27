$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$toolsRoot = Join-Path (Split-Path $project) 'BatteryWatch/android-app/.toolchain'
if ($env:BATTERY_REPORT_TOOLCHAIN) { $toolsRoot = $env:BATTERY_REPORT_TOOLCHAIN }
$jdk = Get-ChildItem -LiteralPath (Join-Path $toolsRoot 'java') -Directory | Select-Object -First 1
$classes = Join-Path $project 'qa/classes'
New-Item -ItemType Directory -Path $classes -Force | Out-Null
$source = Join-Path $project 'app/src/main/java/kr/co/batteryreport'
& (Join-Path $jdk.FullName 'bin/javac.exe') -encoding UTF-8 -d $classes (Join-Path $source 'LogAnalyzer.java') (Join-Path $source 'ReportImages.java') (Join-Path $source 'DocxReports.java') (Join-Path $project 'tools/DesktopPainter.java') (Join-Path $project 'tools/Regression.java')
if ($LASTEXITCODE -ne 0) { throw 'Test compilation failed' }
& (Join-Path $jdk.FullName 'bin/java.exe') '-Djava.awt.headless=true' -cp $classes kr.co.batteryreport.Regression $project
if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed' }
