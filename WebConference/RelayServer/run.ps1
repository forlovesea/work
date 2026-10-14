param(
    [string]$ListenAddress = '127.0.0.1',
    [ValidateRange(1,65535)][int]$Port = 8000,
    [string]$EnvFile = ''
)
$ErrorActionPreference = 'Stop'
$serverPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $serverPython)) {
    # Reuse the existing project environment on this development PC.
    $serverPython = Join-Path (Split-Path -Parent $PSScriptRoot) '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $serverPython)) {
    throw 'Create .venv with Python 3.12 and install requirements.txt first.'
}
$serverArguments = @((Join-Path $PSScriptRoot 'server.py'), '--host', $ListenAddress, '--port', $Port)
if ($EnvFile) { $serverArguments += @('--env-file', $EnvFile) }
& $serverPython @serverArguments
exit $LASTEXITCODE
