using System.Diagnostics;

namespace SafeChild;

internal static class MobileFirewall
{
    private const string Rule = "SafeChild Mobile HTTPS";
    public static async Task ConfigureAsync(string localAddress, bool external = false)
    {
        await RemoveAsync();
        await RunAsync(BuildArguments(localAddress, external, Environment.ProcessPath!));
    }
    internal static string[] BuildArguments(string localAddress, bool external, string executable) =>
        ["advfirewall", "firewall", "add", "rule", $"name={Rule}", "dir=in", "action=allow", "protocol=TCP",
            $"localport={MobileControlServer.Port}", $"localip={localAddress}", external ? "remoteip=any" : "remoteip=LocalSubnet", "profile=private,domain",
            $"program={executable}", "enable=yes"];
    public static Task RemoveAsync() => RunAsync(["advfirewall", "firewall", "delete", "rule", $"name={Rule}"], true);
    private static async Task RunAsync(string[] arguments, bool allowMissing = false)
    {
        var info = new ProcessStartInfo("netsh.exe") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in arguments) info.ArgumentList.Add(argument);
        using var process = Process.Start(info) ?? throw new InvalidOperationException("방화벽 설정을 시작하지 못했습니다.");
        var output = process.StandardOutput.ReadToEndAsync(); var error = process.StandardError.ReadToEndAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        try { await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false); }
        catch { try { process.Kill(); } catch { } throw; }
        var detail = (await output.ConfigureAwait(false)) + (await error.ConfigureAwait(false));
        if (process.ExitCode != 0 && !allowMissing) throw new InvalidOperationException("방화벽 설정 실패. 관리자 권한을 확인하세요. " + detail.Trim());
    }
}
