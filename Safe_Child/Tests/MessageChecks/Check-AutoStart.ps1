$ErrorActionPreference = 'Stop'
Import-Module ScheduledTasks
# Only construct Windows task definitions. Registration/query are intercepted;
# this test never changes the host's Task Scheduler.
function Register-ScheduledTask {
    [CmdletBinding()]
    param($TaskName, $Action, $Trigger, $Principal, $Settings, $Description, [switch]$Force)
    if ($Action.Execute -ne "C:\Program Files\SafeChild's Test\SafeChild.exe") { throw 'Executable escaping mismatch' }
    if ($Action.WorkingDirectory -ne "C:\Program Files\SafeChild's Test") { throw 'Working directory mismatch' }
    if ($Trigger.UserId -ne 'S-1-5-21-1-2-3-1001') { throw 'Logon user mismatch' }
    if ($Principal.LogonType -ne 'Interactive' -or $Principal.RunLevel -ne 'Highest') { throw 'Principal mismatch' }
    if ($Settings.ExecutionTimeLimit -ne 'PT0S' -or $Settings.DisallowStartIfOnBatteries -or $Settings.StopIfGoingOnBatteries) { throw 'Continuous protection settings mismatch' }
    if (-not $Force -or $TaskName -ne 'SafeChild.AutoStart.S-1-5-21-1-2-3-1001') { throw 'Idempotent task identity mismatch' }
    $script:registered = [pscustomobject]@{ State = 'Ready'; Actions = $Action }
}
function Get-ScheduledTask {
    [CmdletBinding()]
    param($TaskName)
    return $script:registered
}
$scriptFile = Join-Path $PSScriptRoot 'bin\Debug\net8.0-windows\AutoStart.check.ps1'
$errors = $null
$tokens = $null
[System.Management.Automation.Language.Parser]::ParseFile($scriptFile, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count) { throw ($errors | Out-String) }
& ([scriptblock]::Create((Get-Content -LiteralPath $scriptFile -Raw)))
if (-not $script:registered) { throw 'Registration was not requested' }
'Auto-start task definition verified; no task was registered.'
