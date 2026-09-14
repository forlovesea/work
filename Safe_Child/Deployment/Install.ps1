$ErrorActionPreference = 'Stop'
try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows 10/11 64-bit is required.' }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $installer = Start-Process powershell.exe -Verb RunAs -PassThru -Wait -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '"')
        exit $installer.ExitCode
    }
    if (Get-Process SafeChild -ErrorAction SilentlyContinue) { throw 'Close SafeChild using its administrator Exit button, then run Setup again.' }
    $installRoot = Join-Path $env:ProgramW6432 'SafeChild'
    $archive = Join-Path $PSScriptRoot 'Payload.zip'
    if (-not (Test-Path -LiteralPath $archive)) { throw 'Payload.zip is missing. Keep all installer files together.' }
    $stage = Join-Path ([IO.Path]::GetTempPath()) ('SafeChild-Setup-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        Expand-Archive -LiteralPath $archive -DestinationPath $stage
        if (-not (Test-Path -LiteralPath (Join-Path $stage 'SafeChild.exe'))) { throw 'Invalid application package.' }
        New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
        Get-ChildItem -LiteralPath $stage | Copy-Item -Destination $installRoot -Recurse -Force
        $shell = New-Object -ComObject WScript.Shell
        $shortcutPaths = @(
            (Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) 'SafeChild.lnk'),
            (Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'SafeChild.lnk')
        )
        foreach ($shortcutPath in $shortcutPaths) {
            $shortcut = $shell.CreateShortcut($shortcutPath)
            $shortcut.TargetPath = Join-Path $installRoot 'SafeChild.exe'
            $shortcut.WorkingDirectory = $installRoot
            $shortcut.Description = 'SafeChild parental control'
            $shortcut.Save()
        }
    }
    finally {
        $resolvedStage = [IO.Path]::GetFullPath($stage)
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        if ($resolvedStage.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and
            [IO.Path]::GetFileName($resolvedStage).StartsWith('SafeChild-Setup-')) {
            Remove-Item -LiteralPath $resolvedStage -Recurse -Force
        }
    }
    Add-Type -AssemblyName System.Windows.Forms
    [Windows.Forms.MessageBox]::Show("Installed to $installRoot`n`nStart SafeChild from the desktop shortcut.`nAdministrator approval is required when starting the app.", 'SafeChild Setup') | Out-Null
    exit 0
}
catch {
    Add-Type -AssemblyName System.Windows.Forms
    [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'SafeChild Setup - Error', 'OK', 'Error') | Out-Null
    exit 1
}
