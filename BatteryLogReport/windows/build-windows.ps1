$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot
$workspace = Split-Path $project
$jdk = Get-ChildItem -LiteralPath (Join-Path $workspace 'BatteryWatch/android-app/.toolchain/java') -Directory | Select-Object -First 1
if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME 'bin/javac.exe'))) { $javaHomeForBuild = $env:JAVA_HOME } else { $javaHomeForBuild = $jdk.FullName }
$build = Join-Path $PSScriptRoot 'build'
$classes = Join-Path $build 'classes'
$package = Join-Path $project 'releases/BatteryLogReport-Windows-x64'
New-Item -ItemType Directory -Path $classes,$package -Force | Out-Null
$shared = Join-Path $project 'app/src/main/java/kr/co/batteryreport'
$sources = @((Join-Path $shared 'LogAnalyzer.java'),(Join-Path $shared 'ReportImages.java'),(Join-Path $shared 'DocxReports.java'),(Join-Path $project 'tools/DesktopPainter.java'))
$sources += @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'src/kr/co/batteryreport') -Filter '*.java' | ForEach-Object FullName)
& (Join-Path $javaHomeForBuild 'bin/javac.exe') --release 8 -encoding UTF-8 -d $classes @sources
if ($LASTEXITCODE -ne 0) { throw 'Windows Java 8 compilation failed.' }
$templates = Join-Path $classes 'templates'
New-Item -ItemType Directory -Path $templates -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $project 'app/src/main/assets/charge.docx'),(Join-Path $project 'app/src/main/assets/outage.docx') -Destination $templates -Force
& (Join-Path $javaHomeForBuild 'bin/jar.exe') cfe (Join-Path $package 'BatteryLogReport.jar') kr.co.batteryreport.DesktopApp -C $classes .
if ($LASTEXITCODE -ne 0) { throw 'Windows JAR packaging failed.' }
$runtimeBase = Join-Path $PSScriptRoot 'tools/runtime-x64-unpacked'
$runtime = Get-ChildItem -LiteralPath $runtimeBase -Directory | Select-Object -First 1
if (-not $runtime -or -not (Test-Path (Join-Path $runtime.FullName 'bin/javaw.exe'))) { throw 'Run download-tools.ps1 first.' }
$runtimeTarget = Join-Path $package 'runtime'
if (-not (Test-Path -LiteralPath $runtimeTarget)) { Copy-Item -LiteralPath $runtime.FullName -Destination $runtimeTarget -Recurse }
$compiler = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'tools/zig-unpacked') -Recurse -Filter zig.exe | Select-Object -First 1
$env:ZIG_GLOBAL_CACHE_DIR = Join-Path $build 'zig-cache-global'
$env:ZIG_LOCAL_CACHE_DIR = Join-Path $build 'zig-cache-local'
& $compiler.FullName cc -target x86_64-windows-gnu -Os -nostdlib -fno-builtin -fno-stack-protector '-Wl,-e,entry' '-Wl,--subsystem,windows' '-Wl,--major-subsystem-version,6' '-Wl,--minor-subsystem-version,1' -o (Join-Path $package 'BatteryLogReport.exe') (Join-Path $PSScriptRoot 'launcher.c') -lkernel32 -luser32
if ($LASTEXITCODE -ne 0) { throw 'Native x64 launcher compilation failed.' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README-Windows.txt'),(Join-Path $PSScriptRoot 'THIRD-PARTY-NOTICES.txt') -Destination $package -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'tools/runtime-x64-selected.json') -Destination (Join-Path $package 'runtime-version.json') -Force
Write-Output ('Windows x64 package built: ' + $package)
