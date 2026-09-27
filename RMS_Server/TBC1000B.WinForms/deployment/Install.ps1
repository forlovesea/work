$ErrorActionPreference = 'Stop'
if (-not [Environment]::Is64BitOperatingSystem) { throw '64-bit Windows is required.' }
$executable = 'TBC1000B_Monitor_v3.2.6.exe'
$target = Join-Path $env:LOCALAPPDATA 'TBC1000B Monitor\3.2.6'
if (Test-Path -LiteralPath (Join-Path $target $executable)) {
    throw "Already installed at $target. Use the existing shortcut or choose a separate portable folder."
}
New-Item -ItemType Directory -Path $target -Force | Out-Null
foreach ($item in @($executable, 'Assets', 'Licenses', '사용안내.txt', 'SHA256SUMS.txt', 'Install.cmd', 'Install.ps1')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $item) -Destination $target -Recurse -Force
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'TBC1000B Monitor v3.2.6.lnk'))
$shortcut.TargetPath = Join-Path $target $executable
$shortcut.WorkingDirectory = $target
$shortcut.IconLocation = "$target\$executable,0"
$shortcut.Save()
Write-Host "Installed: $target"
