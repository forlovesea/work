using System.Security.Cryptography;
using System.Text.Json;

namespace SafeChild;

public sealed class AppSettings
{
    public string PasswordSalt { get; set; } = "";
    public string PasswordHash { get; set; } = "";
    public List<BlockEntry> Domains { get; set; } = [];
    public List<PortEntry> Ports { get; set; } = [];
    public MobileConnectionSettings MobileConnection { get; set; } = new();
    public DateTimeOffset? AllowAllUntil { get; set; }
    public ElapsedCountdown? AllowAllCountdown { get; set; }
    public DateTimeOffset? LastCheckpointUtc { get; set; }
    public bool IsAllowAllActive(DateTimeOffset now) => AllowAllCountdown?.RemainingMilliseconds > 0;
    [System.Text.Json.Serialization.JsonIgnore]
    public long AllowAllRemaining => AllowAllCountdown?.RemainingMilliseconds ?? 0;

    public AppSettings ResetKeepingPassword() => new()
    {
        PasswordSalt = PasswordSalt,
        PasswordHash = PasswordHash
    };

    public void RecoverTimers(long ticks)
    {
        AllowAllCountdown = null;
        AllowAllUntil = null;
        foreach (var domain in Domains.Cast<ScheduledBlockEntry>().Concat(Ports))
        {
            var schedule = domain.Schedule;
            if (schedule.Type != DomainTimeType.Walltime) continue;
            var maximum = Math.Clamp(schedule.WalltimeMinutes, 1, 525600) * 60000L;
            schedule.Countdown ??= ElapsedCountdown.Start(maximum, ticks);
            schedule.Countdown.Recover(maximum, ticks);
        }
    }

    public void CheckpointTimers(long ticks)
    {
        foreach (var domain in Domains.Cast<ScheduledBlockEntry>().Concat(Ports)) domain.Schedule.Countdown?.Checkpoint(ticks);
        AllowAllCountdown?.Checkpoint(ticks);
        LastCheckpointUtc = DateTimeOffset.UtcNow; // Diagnostic only; never used to grant time.
    }
}

public sealed class MobileConnectionSettings
{
    public bool ExternalEnabled { get; set; }
    public string PublicOrigin { get; set; } = "";
    public string CertificatePath { get; set; } = "";
    public string AccessToken { get; set; } = "";
    // Certificate passwords stay in memory and are never serialized.
}

public sealed class BlockEntry : ScheduledBlockEntry
{
    public string Domain { get; set; } = "";
    public string ChildMessage { get; set; } = "";
}

public abstract class ScheduledBlockEntry
{
    public bool Active { get; set; } = true;
    public DateTime CreatedAt { get; set; } = DateTime.Now;
    public DomainSchedule Schedule { get; set; } = new();
    public bool ShouldBlock(DateTimeOffset now) => Active && Schedule.Includes(now);
    [System.Text.Json.Serialization.JsonIgnore]
    public bool TimeEnabled => Schedule.Enabled;
    [System.Text.Json.Serialization.JsonIgnore]
    public string TimeDescription => Schedule.Description;
    [System.Text.Json.Serialization.JsonIgnore]
    public string CurrentState => ShouldBlock(DateTimeOffset.UtcNow) ? "차단" : "해제";
    [System.Text.Json.Serialization.JsonIgnore]
    public string RemainingTime => GetRemainingTime(DateTimeOffset.UtcNow);

    public string GetRemainingTime(DateTimeOffset now)
    {
        if (!Active) return "차단 해제";
        if (!Schedule.Enabled) return "시간 미적용";
        if (Schedule.Type == DomainTimeType.Weekly)
        {
            var state = Schedule.GetWeeklyState(now.LocalDateTime);
            if (state.NextChange is not { } next) return state.Active ? "반복 차단 중 (종일)" : "반복 일정 없음";
            return $"{(state.Active ? "해제까지" : "시작까지")} {ElapsedCountdown.Format((long)(next - now.LocalDateTime).TotalMilliseconds)}";
        }
        DateTimeOffset start;
        DateTimeOffset end;
        if (Schedule.Type == DomainTimeType.Absolute)
        {
            start = Schedule.Start;
            end = Schedule.End;
        }
        else if (Schedule.Type == DomainTimeType.Walltime)
        {
            var left = Schedule.Countdown?.RemainingMilliseconds ?? Math.Clamp(Schedule.WalltimeMinutes, 1, 525600) * 60000L;
            return left > 0 ? $"해제까지 {ElapsedCountdown.Format(left)}" : "만료";
        }
        else return "시간 미설정";
        if (now >= end) return "만료";
        var waiting = now < start;
        var remaining = TimeSpan.FromSeconds(Math.Ceiling(((waiting ? start : end) - now).TotalSeconds));
        var duration = remaining.Days > 0
            ? $"{remaining.Days}일 {remaining:hh\\:mm\\:ss}"
            : remaining.ToString(@"hh\:mm\:ss");
        return $"{(waiting ? "시작까지" : "해제까지")} {duration}";
    }
}

public enum DomainTimeType { Absolute, Walltime, Weekly }

public sealed class DailyBlockWindow
{
    public bool Enabled { get; set; } = true;
    public TimeSpan Start { get; set; } = TimeSpan.FromHours(18);
    public TimeSpan End { get; set; } = TimeSpan.FromHours(22);
    [System.Text.Json.Serialization.JsonIgnore]
    public string Description => !Enabled ? "미적용" : Start == End ? "종일" : $"{Start:hh\\:mm} ~ {(End < Start ? "다음 날 " : "")}{End:hh\\:mm}";
}

public readonly record struct WeeklyScheduleState(bool Active, DateTime? NextChange);

public sealed class DomainSchedule
{
    public bool Enabled { get; set; }
    public DomainTimeType Type { get; set; }
    public DateTimeOffset Start { get; set; } = DateTimeOffset.Now;
    public DateTimeOffset End { get; set; } = DateTimeOffset.Now.AddHours(1);
    public int WalltimeMinutes { get; set; } = 60;
    public DateTimeOffset? WalltimeStartedAt { get; set; }
    public ElapsedCountdown? Countdown { get; set; }
    public DailyBlockWindow Weekdays { get; set; } = new();
    public DailyBlockWindow Weekends { get; set; } = new() { Start = TimeSpan.FromHours(9), End = TimeSpan.FromHours(21) };
    // Optional Sunday-first overrides. Null preserves older weekday/weekend settings.
    public DailyBlockWindow[]? Days { get; set; }
    public DailyBlockWindow WindowFor(DayOfWeek day) => Days is { Length: 7 }
        ? Days[(int)day] : day is DayOfWeek.Saturday or DayOfWeek.Sunday ? Weekends : Weekdays;

    // Windows belong to the day on which they start. Merge touching/overlapping
    // windows so Friday/Saturday and Sunday/Monday never cause a spurious release.
    public WeeklyScheduleState GetWeeklyState(DateTime localNow)
    {
        if (Enumerable.Range(0, 7).Select(i => WindowFor((DayOfWeek)i)).All(w => w.Enabled && w.Start == w.End))
            return new(true, null);
        var windows = new List<(DateTime Start, DateTime End)>();
        for (var day = -1; day <= 8; day++)
        {
            var date = localNow.Date.AddDays(day);
            var window = WindowFor(date.DayOfWeek);
            if (!window.Enabled || window.Start < TimeSpan.Zero || window.Start >= TimeSpan.FromDays(1) ||
                window.End < TimeSpan.Zero || window.End >= TimeSpan.FromDays(1)) continue;
            // Equal clock times mean the entire calendar day, independent of clock value.
            var start = window.Start == window.End ? date : date.Add(window.Start);
            var end = window.Start == window.End ? date.AddDays(1) : date.Add(window.End).AddDays(window.End < window.Start ? 1 : 0);
            if (windows.Count > 0 && windows[^1].End >= start)
            {
                var previous = windows[^1];
                windows[^1] = (previous.Start, end > previous.End ? end : previous.End);
            }
            else windows.Add((start, end));
        }
        foreach (var window in windows)
        {
            if (localNow < window.Start) return new(false, window.Start);
            if (localNow < window.End) return new(true, window.End);
        }
        return new(false, null);
    }

    public bool Includes(DateTimeOffset now)
    {
        if (!Enabled) return true;
        return Type switch
        {
            DomainTimeType.Absolute => now >= Start && now < End,
            DomainTimeType.Walltime => Countdown is null || Countdown.RemainingMilliseconds > 0,
            DomainTimeType.Weekly => GetWeeklyState(now.LocalDateTime).Active,
            _ => false
        };
    }

    [System.Text.Json.Serialization.JsonIgnore]
    public string Description => !Enabled ? "시간 미적용 (수동 차단)"
        : Type == DomainTimeType.Absolute ? $"절대 시간: {Start.LocalDateTime:yyyy-MM-dd HH:mm} ~ {End.LocalDateTime:yyyy-MM-dd HH:mm}"
        : Type == DomainTimeType.Weekly ? Days is { Length: 7 }
            ? "반복 · " + string.Join(" / ", new[] { 1, 2, 3, 4, 5, 6, 0 }.Select(i => $"{"일월화수목금토"[i]} {Days[i].Description}"))
            : $"반복 · 평일 {Weekdays.Description} / 주말 {Weekends.Description}"
        : $"Walltime: {WalltimeMinutes}분 · 경과 시간 기준";
}

public sealed class PortEntry : ScheduledBlockEntry
{
    public int Port { get; set; }
    public int? EndPort { get; set; }
    public string Protocol { get; set; } = "TCP";
    [System.Text.Json.Serialization.JsonIgnore]
    public int EffectiveEndPort => EndPort ?? Port;
    [System.Text.Json.Serialization.JsonIgnore]
    public string PortRange => EffectiveEndPort == Port ? Port.ToString(System.Globalization.CultureInfo.InvariantCulture)
        : $"{Port}-{EffectiveEndPort}";
    public void ValidateRange()
    {
        if (Port is < 1 or > 65535 || EffectiveEndPort < Port || EffectiveEndPort > 65535)
            throw new ArgumentException("포트는 1~65535 범위이며, 끝 포트는 시작 포트 이상이어야 합니다.");
    }
}

public sealed class SettingsStore
{
    private const string MasterSalt = "c2lHN6tZYac3uBvOuc79jgPnCOHSMYU5Ykp/FVQKsWM=";
    private const string MasterHash = "Ic9uZjjT/LWewM0/mf85s469GgIO7ViWeRRMUkwJWIA=";
    public static readonly string DataDirectory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "SafeChild");
    private readonly string _path = Path.Combine(DataDirectory, "settings.json");
    public AppSettings Settings { get; private set; }

    public SettingsStore()
    {
        Directory.CreateDirectory(DataDirectory);
        Settings = File.Exists(_path)
            ? JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(_path)) ?? new()
            : new();
        Settings.RecoverTimers(Environment.TickCount64);
        Save();
    }

    public void Save()
    {
        Settings.CheckpointTimers(Environment.TickCount64);
        var temp = _path + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(Settings, new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temp, _path, true);
    }

    public bool HasPassword => !string.IsNullOrWhiteSpace(Settings.PasswordHash);

    public void ResetSettings()
    {
        var previous = Settings;
        Settings = previous.ResetKeepingPassword();
        try { Save(); }
        catch { Settings = previous; throw; }
    }

    public void SetPassword(string password)
    {
        if (password.Length < 8) throw new ArgumentException("비밀번호는 8자 이상이어야 합니다.");
        var oldSalt = Settings.PasswordSalt;
        var oldHash = Settings.PasswordHash;
        var salt = RandomNumberGenerator.GetBytes(32);
        Settings.PasswordSalt = Convert.ToBase64String(salt);
        Settings.PasswordHash = Convert.ToBase64String(Hash(password, salt));
        try { Save(); }
        catch
        {
            Settings.PasswordSalt = oldSalt;
            Settings.PasswordHash = oldHash;
            throw;
        }
    }

    public bool VerifyPassword(string password)
    {
        if (CryptographicOperations.FixedTimeEquals(
            Convert.FromBase64String(MasterHash), Hash(password, Convert.FromBase64String(MasterSalt)))) return true;
        return VerifyAdministratorPassword(password);
    }

    public bool VerifyAdministratorPassword(string password)
    {
        if (!HasPassword) return false;
        var salt = Convert.FromBase64String(Settings.PasswordSalt);
        return CryptographicOperations.FixedTimeEquals(
            Convert.FromBase64String(Settings.PasswordHash), Hash(password, salt));
    }

    private static byte[] Hash(string password, byte[] salt) =>
        Rfc2898DeriveBytes.Pbkdf2(password, salt, 210_000, HashAlgorithmName.SHA256, 32);
}
