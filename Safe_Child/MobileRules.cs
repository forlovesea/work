using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace SafeChild;

public sealed record MobileWindow(bool Enabled, string Start, string End);
public sealed record MobileSchedule(bool Enabled, int Type, string Start, string End, int Minutes,
    MobileWindow[] Days, bool Restart = false);
public sealed record MobileRule(string Domain, bool Active, MobileSchedule Schedule, string Version,
    string Description, string State, string Remaining);
public sealed record MobileRulesResult(MobileRule[] Rules, string TimeZone, string PcTime, bool AllowAll, string? Error);
public sealed record MobileRuleCommand(string Operation, string? OriginalDomain, string? Version,
    string? Domain, bool Active, MobileSchedule? Schedule);
public sealed class MobileRuleException(int status, string message) : Exception(message)
{
    public int Status { get; } = status;
}

// Only editable rule data is exposed; credentials and timer internals never leave the PC.
public static class MobileRules
{
    public static MobileSchedule ScheduleView(DomainSchedule s) => new(s.Enabled, (int)s.Type,
        s.Start.LocalDateTime.ToString("yyyy-MM-ddTHH:mm:ss"), s.End.LocalDateTime.ToString("yyyy-MM-ddTHH:mm:ss"),
        s.WalltimeMinutes, Enumerable.Range(0, 7).Select(i =>
        {
            var w = s.WindowFor((DayOfWeek)i);
            return new MobileWindow(w.Enabled, w.Start.ToString(@"hh\:mm"), w.End.ToString(@"hh\:mm"));
        }).ToArray());

    public static string Version(BlockEntry e) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
        JsonSerializer.Serialize(new { e.Domain, e.Active, e.CreatedAt, e.ChildMessage, Schedule = ScheduleView(e.Schedule),
            e.Schedule.WalltimeStartedAt }))));

    public static MobileRulesResult Read(AppSettings settings, string? error = null)
    {
        var now = DateTimeOffset.UtcNow;
        var allow = settings.IsAllowAllActive(now);
        return new(settings.Domains.Select(e => new MobileRule(e.Domain, e.Active, ScheduleView(e.Schedule), Version(e),
            e.Schedule.Description, error is not null ? "적용 확인 필요" : allow ? "전체 일시 허용 중" : e.ShouldBlock(now) ? "차단" : "해제",
            e.GetRemainingTime(now))).ToArray(), TimeZoneInfo.Local.DisplayName, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"), allow, error);
    }

    public static void Execute(AppSettings settings, MobileRuleCommand command, Func<string, string> normalize, Action save)
    {
        if (command.Operation is not ("save" or "delete")) throw new MobileRuleException(400, "지원하지 않는 작업입니다.");
        var existing = command.OriginalDomain is null ? null : settings.Domains.FirstOrDefault(e => e.Domain == command.OriginalDomain);
        if (command.OriginalDomain is not null && (existing is null || Version(existing) != command.Version))
            throw new MobileRuleException(409, "PC 또는 다른 휴대폰에서 설정이 변경되었습니다. 목록을 새로고침하고 다시 편집하세요.");
        if (command.Operation == "delete" && existing is null) throw new MobileRuleException(400, "삭제할 사이트를 선택하세요.");

        BlockEntry? replacement = null;
        if (command.Operation == "save")
        {
            if (string.IsNullOrWhiteSpace(command.Domain) || command.Domain.Length > 2048)
                throw new MobileRuleException(400, "사이트 주소를 입력하세요.");
            string domain;
            try { domain = normalize(command.Domain); }
            catch (ArgumentException) { throw new MobileRuleException(400, "올바른 사이트 주소를 입력하세요."); }
            if (domain.Length > 253 || Uri.CheckHostName(domain) != UriHostNameType.Dns || !domain.Contains('.'))
                throw new MobileRuleException(400, "example.com 형식의 도메인을 입력하세요.");
            if (settings.Domains.Any(e => e != existing && e.Domain.Equals(domain, StringComparison.OrdinalIgnoreCase)))
                throw new MobileRuleException(409, "이미 등록된 사이트입니다.");
            replacement = new BlockEntry { Domain = domain, Active = command.Active,
                CreatedAt = existing?.CreatedAt ?? DateTime.Now, ChildMessage = existing?.ChildMessage ?? "",
                Schedule = BuildSchedule(command.Schedule, existing?.Schedule) };
        }
        var before = settings.Domains;
        var after = before.ToList();
        if (existing is not null)
        {
            var index = after.IndexOf(existing);
            if (replacement is null) after.RemoveAt(index); else after[index] = replacement;
        }
        else after.Add(replacement!);
        settings.Domains = after;
        try { save(); }
        catch { settings.Domains = before; throw; }
    }

    public static DomainSchedule BuildSchedule(MobileSchedule? input, DomainSchedule? previous)
    {
        if (input is null || input.Type is < 0 or > 2 || input.Minutes is < 1 or > 525600 || input.Days is not { Length: 7 })
            throw new MobileRuleException(400, "시간 설정 값을 확인하세요.");
        DateTimeOffset ParseDate(string value)
        {
            if (!DateTime.TryParseExact(value, new[] { "yyyy-MM-ddTHH:mm", "yyyy-MM-ddTHH:mm:ss" }, CultureInfo.InvariantCulture,
                DateTimeStyles.None, out var date) || date.Year < 1753 || date.Year > 9998 || TimeZoneInfo.Local.IsInvalidTime(date))
                throw new MobileRuleException(400, "PC 현지 시각 기준으로 올바른 날짜와 시간을 입력하세요.");
            return new DateTimeOffset(date, TimeZoneInfo.Local.GetUtcOffset(date));
        }
        var start = ParseDate(input.Start); var end = ParseDate(input.End);
        if (input.Enabled && input.Type == 0 && end <= start) throw new MobileRuleException(400, "종료 시각은 시작보다 늦어야 합니다.");
        var days = input.Days.Select(w =>
        {
            if (w is null || !TimeSpan.TryParseExact(w.Start, @"hh\:mm", CultureInfo.InvariantCulture, out var a) ||
                !TimeSpan.TryParseExact(w.End, @"hh\:mm", CultureInfo.InvariantCulture, out var b) || a >= TimeSpan.FromDays(1) || b >= TimeSpan.FromDays(1))
                throw new MobileRuleException(400, "요일별 시각은 00:00~23:59로 입력하세요.");
            return new DailyBlockWindow { Enabled = w.Enabled, Start = a, End = b };
        }).ToArray();
        var restart = input.Enabled && input.Type == 1 && (input.Restart || previous is null || !previous.Enabled ||
            previous.Type != DomainTimeType.Walltime || previous.WalltimeMinutes != input.Minutes || previous.Countdown is null);
        return new DomainSchedule { Enabled = input.Enabled, Type = (DomainTimeType)input.Type, Start = start, End = end,
            WalltimeMinutes = input.Minutes, Days = days, Weekdays = previous?.Weekdays ?? new(), Weekends = previous?.Weekends ?? new(),
            Countdown = restart ? ElapsedCountdown.Start(input.Minutes * 60000L) : previous?.Countdown,
            WalltimeStartedAt = restart ? DateTimeOffset.UtcNow : previous?.WalltimeStartedAt };
    }
}
