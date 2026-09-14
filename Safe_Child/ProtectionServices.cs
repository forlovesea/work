using System.Diagnostics;
using System.Globalization;
using Microsoft.Data.Sqlite;

namespace SafeChild;

public static class BlockingService
{
    private const string Start = "# SafeChild BEGIN";
    private const string End = "# SafeChild END";

    public static string NormalizeDomain(string input)
    {
        input = input.Trim();
        if (!input.Contains("://")) input = "https://" + input;
        if (!Uri.TryCreate(input, UriKind.Absolute, out var uri) || string.IsNullOrWhiteSpace(uri.Host))
            throw new ArgumentException("올바른 URL 또는 도메인을 입력하세요.");
        return uri.IdnHost.TrimEnd('.').ToLowerInvariant();
    }

    public static void ApplyDomains(IEnumerable<BlockEntry> entries, DateTimeOffset? at = null)
    {
        var path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), @"drivers\etc\hosts");
        var text = File.ReadAllText(path);
        var start = text.IndexOf(Start, StringComparison.Ordinal);
        var end = text.IndexOf(End, StringComparison.Ordinal);
        if (start >= 0 && end >= start)
            text = text.Remove(start, end + End.Length - start).TrimEnd() + Environment.NewLine;

        var now = at ?? DateTimeOffset.UtcNow;
        var domains = entries.Where(x => x.ShouldBlock(now)).Select(x => x.Domain).Distinct(StringComparer.OrdinalIgnoreCase);
        var lines = domains.SelectMany(d => new[] { $"0.0.0.0 {d}", $"0.0.0.0 www.{d}" }).Distinct();
        text += $"{Start}{Environment.NewLine}{string.Join(Environment.NewLine, lines)}{Environment.NewLine}{End}{Environment.NewLine}";
        File.WriteAllText(path, text);
        Run("ipconfig.exe", "/flushdns");
    }

    public static void ApplyPorts(IEnumerable<PortEntry> entries, DateTimeOffset? at = null)
    {
        var now = at ?? DateTimeOffset.UtcNow;
        var active = entries.Where(x => x.ShouldBlock(now)).ToList();
        foreach (var entry in active) entry.ValidateRange();
        Run("netsh.exe", "advfirewall firewall delete rule name=\"SafeChild Port Block\"");
        foreach (var entry in active)
        {
            var protocol = entry.Protocol is "UDP" ? "UDP" : "TCP";
            Run("netsh.exe", $"advfirewall firewall add rule name=\"SafeChild Port Block\" dir=out action=block protocol={protocol} remoteport={entry.PortRange} profile=any enable=yes");
        }
    }

    private static void Run(string file, string arguments)
    {
        using var process = Process.Start(new ProcessStartInfo(file, arguments)
        {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardError = true, RedirectStandardOutput = true
        }) ?? throw new InvalidOperationException($"{file}을 실행할 수 없습니다.");
        var outputTask = process.StandardOutput.ReadToEndAsync();
        var errorTask = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(15_000))
        {
            try { process.Kill(); } catch { }
            throw new TimeoutException($"{file} 실행 시간이 15초를 초과했습니다.");
        }
        var error = errorTask.GetAwaiter().GetResult();
        _ = outputTask.GetAwaiter().GetResult();
        if (process.ExitCode != 0 && !arguments.Contains("delete rule"))
            throw new InvalidOperationException(error.Length > 0 ? error : $"명령 실패 ({process.ExitCode})");
    }
}

public sealed record VisitRow(string Browser, string Url, string Title, DateTime VisitedAt, int DurationSeconds);

public sealed class BrowserHistoryService
{
    private readonly string _database = Path.Combine(SettingsStore.DataDirectory, "history.db");

    public BrowserHistoryService()
    {
        using var connection = OpenOwn();
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = """
            CREATE TABLE IF NOT EXISTS visits(
              browser TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL,
              visited_at TEXT NOT NULL, PRIMARY KEY(browser,url,visited_at));
            CREATE INDEX IF NOT EXISTS ix_visits_at ON visits(visited_at DESC);
            """;
        command.ExecuteNonQuery();
    }

    public async Task<int> CollectAsync(CancellationToken cancellationToken = default)
    {
        var total = 0;
        foreach (var (browser, root) in BrowserRoots())
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!Directory.Exists(root)) continue;
            var profiles = Directory.EnumerateDirectories(root)
                .Where(p => Path.GetFileName(p) == "Default" || Path.GetFileName(p).StartsWith("Profile "));
            foreach (var profile in profiles)
                total += await ImportAsync(browser, Path.Combine(profile, "History"), cancellationToken);
        }
        return total;
    }

    public List<VisitRow> Read(DateTime from, DateTime to, string search)
    {
        using var connection = OpenOwn(); connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = """
            SELECT browser,url,title,visited_at FROM visits
            WHERE visited_at >= $from AND visited_at < $to
              AND ($search='' OR url LIKE $like OR title LIKE $like)
            ORDER BY visited_at DESC LIMIT 10000;
            """;
        command.Parameters.AddWithValue("$from", from.ToUniversalTime().ToString("O"));
        command.Parameters.AddWithValue("$to", to.ToUniversalTime().ToString("O"));
        command.Parameters.AddWithValue("$search", search);
        command.Parameters.AddWithValue("$like", $"%{search}%");
        var raw = new List<(string Browser, string Url, string Title, DateTime At)>();
        using var reader = command.ExecuteReader();
        while (reader.Read()) raw.Add((reader.GetString(0), reader.GetString(1), reader.GetString(2), DateTime.Parse(reader.GetString(3), null, DateTimeStyles.RoundtripKind).ToLocalTime()));
        return raw.Select((x, i) =>
        {
            var nextVisit = raw.Take(i).FirstOrDefault(y => y.Browser == x.Browser);
            var seconds = nextVisit == default ? 0 :
                (int)Math.Clamp((nextVisit.At - x.At).TotalSeconds, 0, 1800);
            return new VisitRow(x.Browser, x.Url, x.Title, x.At, seconds);
        }).ToList();
    }

    private async Task<int> ImportAsync(string browser, string source, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!File.Exists(source)) return 0;
        var copy = Path.Combine(Path.GetTempPath(), $"safechild-{Guid.NewGuid():N}.db");
        try
        {
            File.Copy(source, copy, true);
            await using var sourceDb = new SqliteConnection($"Data Source={copy};Mode=ReadOnly");
            await sourceDb.OpenAsync();
            await using var read = sourceDb.CreateCommand();
            read.CommandText = """
                SELECT u.url, COALESCE(u.title,''), v.visit_time FROM visits v
                JOIN urls u ON u.id=v.url WHERE v.visit_time>0 ORDER BY v.visit_time DESC LIMIT 50000;
                """;
            await using var reader = await read.ExecuteReaderAsync();
            await using var target = OpenOwn(); await target.OpenAsync();
            await using var transaction = await target.BeginTransactionAsync();
            var count = 0;
            while (await reader.ReadAsync())
            {
                cancellationToken.ThrowIfCancellationRequested();
                var chromeMicroseconds = reader.GetInt64(2);
                var visited = DateTime.UnixEpoch.AddSeconds(-11644473600L).AddTicks(chromeMicroseconds * 10);
                if (visited < DateTime.UtcNow.AddDays(-365)) continue;
                await using var insert = target.CreateCommand();
                insert.Transaction = (SqliteTransaction)transaction;
                insert.CommandText = "INSERT OR IGNORE INTO visits VALUES($b,$u,$t,$v)";
                insert.Parameters.AddWithValue("$b", browser);
                insert.Parameters.AddWithValue("$u", reader.GetString(0));
                insert.Parameters.AddWithValue("$t", reader.GetString(1));
                insert.Parameters.AddWithValue("$v", DateTime.SpecifyKind(visited, DateTimeKind.Utc).ToString("O"));
                count += await insert.ExecuteNonQueryAsync();
            }
            cancellationToken.ThrowIfCancellationRequested();
            await transaction.CommitAsync(cancellationToken);
            return count;
        }
        catch (IOException) { return 0; }
        catch (SqliteException) { return 0; }
        finally { try { File.Delete(copy); } catch { } }
    }

    private SqliteConnection OpenOwn() => new($"Data Source={_database}");
    private static IEnumerable<(string, string)> BrowserRoots()
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        yield return ("Chrome", Path.Combine(local, @"Google\Chrome\User Data"));
        yield return ("Edge", Path.Combine(local, @"Microsoft\Edge\User Data"));
    }
}
