param([string]$Python = '')
$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $Python = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $Python)) { $Python = 'python' }
}
& $Python -c "import sys; assert sys.version_info[:2] == (3, 12), 'Python 3.12 is required'"
if ($LASTEXITCODE -ne 0) { throw 'Specify Python 3.12 with -Python.' }
& $Python -m venv (Join-Path $PSScriptRoot '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$requirements = Get-ChildItem -LiteralPath $PSScriptRoot -Directory | ForEach-Object {
    $candidate = Join-Path $_.FullName 'requirements-dev.txt'
    if (Test-Path -LiteralPath $candidate) { $candidate }
}
if (@($requirements).Count -ne 1) { throw 'Cannot identify server requirements.' }
# Apply to build subprocesses too; avoid the inherited machine pip cache.
$previous = @{}
foreach ($name in @('PIP_NO_CACHE_DIR', 'PIP_DISABLE_PIP_VERSION_CHECK', 'PIP_PROGRESS_BAR')) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    $env:PIP_NO_CACHE_DIR = '1'
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    $env:PIP_PROGRESS_BAR = 'off'
    & $venvPython -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $venvPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency validation failed.' }
} finally {
    foreach ($name in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
