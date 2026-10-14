param(
    [string]$ListenAddress = '127.0.0.1',
    [ValidateRange(1,65535)][int]$Port = 8000,
    [string]$EnvFile = ''
)
# Compatibility launcher: all application files live in the relay directory.
$serverDirectories = @(Get-ChildItem -LiteralPath $PSScriptRoot -Directory | Where-Object {
    Test-Path -LiteralPath (Join-Path $_.FullName 'server.py')
})
if ($serverDirectories.Count -ne 1) { throw 'Cannot identify server directory.' }
& (Join-Path $serverDirectories[0].FullName 'run.ps1') @PSBoundParameters
exit $LASTEXITCODE
