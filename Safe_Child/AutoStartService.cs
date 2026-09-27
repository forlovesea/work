using System.Diagnostics;
using System.Security.Principal;
using System.Text;

namespace SafeChild;

internal static class AutoStartService
{
    internal static string BuildScript(string executable, string sid, bool enable)
    {
        static string Quote(string value) => "'" + value.Replace("'", "''") + "'";
        var name = Quote("SafeChild.AutoStart." + sid);
        if (!enable) return $"$ErrorActionPreference='Stop'; $task=Get-ScheduledTask -TaskName {name} -ErrorAction SilentlyContinue; if($task){{Unregister-ScheduledTask -TaskName {name} -Confirm:$false}}";
        return $$"""
            $ErrorActionPreference = 'Stop'
            $action = New-ScheduledTaskAction -Execute {{Quote(executable)}} -WorkingDirectory {{Quote(Path.GetDirectoryName(executable)!)}}
            $trigger = New-ScheduledTaskTrigger -AtLogOn -User {{Quote(sid)}}
            $principal = New-ScheduledTaskPrincipal -UserId {{Quote(sid)}} -LogonType Interactive -RunLevel Highest
            $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
            Register-ScheduledTask -TaskName {{name}} -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'SafeChild: start when the configured Windows user signs in.' -Force | Out-Null
            $registered = Get-ScheduledTask -TaskName {{name}} -ErrorAction Stop
            if ($registered.State -eq 'Disabled' -or $registered.Actions.Execute -ne {{Quote(executable)}}) { throw 'Auto-start verification failed.' }
            """;
    }

    public static async Task ConfigureAsync(bool enable)
    {
        using var identity = WindowsIdentity.GetCurrent();
        var sid = identity.User?.Value ?? throw new InvalidOperationException("Windows 계정을 확인할 수 없습니다.");
        var executable = Path.Combine(AppContext.BaseDirectory, "SafeChild.exe");
        if (enable && !File.Exists(executable)) throw new FileNotFoundException("자동 실행할 프로그램을 찾을 수 없습니다.", executable);
        var info = new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), @"WindowsPowerShell\v1.0\powershell.exe"))
        {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        info.ArgumentList.Add("-NoProfile"); info.ArgumentList.Add("-NonInteractive"); info.ArgumentList.Add("-EncodedCommand");
        info.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes("[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + BuildScript(executable, sid, enable))));
        using var process = Process.Start(info) ?? throw new InvalidOperationException("Windows 자동 실행 설정을 시작하지 못했습니다.");
        var output = process.StandardOutput.ReadToEndAsync();
        var error = process.StandardError.ReadToEndAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        try { await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false); }
        catch (OperationCanceledException)
        {
            try { process.Kill(); } catch { }
            throw new TimeoutException("자동 실행 설정 확인 시간이 초과되었습니다. 작업 스케줄러 상태를 확인한 뒤 다시 눌러주세요.");
        }
        var detail = (await error.ConfigureAwait(false)) + (await output.ConfigureAwait(false));
        if (process.ExitCode != 0) throw new InvalidOperationException("Windows 자동 실행 설정에 실패했습니다.\n" + detail.Trim());
    }
}
