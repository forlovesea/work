$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot
$name = 'BatteryLogReport-Windows-x64-1.0.1'
$package = Join-Path $project ('releases/' + $name)
$archive = Join-Path $project ('releases/' + $name + '.zip')
$temporary = $archive + '.tmp'
if (Test-Path -LiteralPath $temporary) { throw 'Temporary archive already exists; inspect it before rerunning.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$writer = [IO.Compression.ZipFile]::Open($temporary,[IO.Compression.ZipArchiveMode]::Create)
try {
    $base = [IO.Path]::GetFullPath($package).TrimEnd('\')
    foreach ($file in Get-ChildItem -LiteralPath $package -Recurse -File) {
        $relative = $file.FullName.Substring($base.Length + 1).Replace('\','/')
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($writer,$file.FullName,($name + '/' + $relative),[IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally { $writer.Dispose() }
Move-Item -LiteralPath $temporary -Destination $archive -Force
$sum = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
[IO.File]::WriteAllText((Join-Path $project 'releases/Windows-x64-SHA256SUMS.txt'), "$sum  $name.zip`n")
$check = [IO.Compression.ZipFile]::OpenRead($archive)
try {
    foreach ($entry in @('BatteryLogReport.exe','BatteryLogReport.jar','runtime/bin/javaw.exe','runtime/bin/server/jvm.dll','runtime/LICENSE','README-Windows.txt')) {
        if (-not $check.GetEntry($name + '/' + $entry)) { throw "Missing release entry: $entry" }
    }
    Write-Output ('Release ZIP verified: ' + $check.Entries.Count + ' files; ' + (Get-Item -LiteralPath $archive).Length + ' bytes')
} finally { $check.Dispose() }
