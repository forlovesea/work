using System.Net;

namespace SafeChild;

public sealed class HostsStatus
{
    public static string FilePath => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), @"drivers\etc\hosts");
    private readonly Dictionary<string, List<IPAddress>> _addresses = new(StringComparer.OrdinalIgnoreCase);
    public string? Error { get; private init; }
    public DateTime CheckedAt { get; } = DateTime.Now;

    public static HostsStatus Read(string? path = null)
    {
        try { return Parse(File.ReadAllText(path ?? FilePath)); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Security.SecurityException)
        { return new HostsStatus { Error = ex.Message }; }
    }

    public static HostsStatus Parse(string text)
    {
        var result = new HostsStatus();
        foreach (var line in text.Split('\n'))
        {
            var fields = line.Split('#')[0].Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (fields.Length < 2 || !IPAddress.TryParse(fields[0], out var address)) continue;
            foreach (var alias in fields.Skip(1))
            {
                var host = alias.TrimEnd('.');
                if (!result._addresses.TryGetValue(host, out var addresses))
                    result._addresses[host] = addresses = [];
                addresses.Add(address);
            }
        }
        return result;
    }

    private static bool IsBlocking(IPAddress address)
    {
        if (address.IsIPv4MappedToIPv6) address = address.MapToIPv4();
        return address.Equals(IPAddress.Any) || address.Equals(IPAddress.IPv6Any) || IPAddress.IsLoopback(address);
    }

    public (string Text, bool Matches, string Detail) Describe(string domain, bool expectedBlocked)
    {
        if (Error is not null) return ("확인 실패", false, Error);
        var hosts = new[] { domain, "www." + domain };
        var blocked = 0;
        var conflict = false;
        var details = new List<string>();
        foreach (var host in hosts)
        {
            _addresses.TryGetValue(host.TrimEnd('.'), out var addresses);
            var hasBlock = addresses?.Any(IsBlocking) == true;
            var hasOther = addresses?.Any(a => !IsBlocking(a)) == true;
            if (hasBlock) blocked++;
            conflict |= hasBlock && hasOther;
            details.Add($"{host}: {(addresses is null ? "항목 없음" : string.Join(", ", addresses))}");
        }
        var state = conflict ? "충돌 확인 필요" : blocked == hosts.Length ? "차단" : blocked == 0 ? "해제" : "일부 차단";
        var matches = !conflict && (expectedBlocked ? blocked == hosts.Length : blocked == 0);
        return (state + (matches ? "" : " (설정 불일치)"), matches, string.Join(Environment.NewLine, details));
    }
}
