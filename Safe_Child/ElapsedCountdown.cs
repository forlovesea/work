using System.Text.Json.Serialization;

namespace SafeChild;

// A persisted remaining duration, never a deadline derived from the PC calendar.
public sealed class ElapsedCountdown
{
    public long SavedRemainingMilliseconds { get; set; }
    private long _anchor = Environment.TickCount64;
    [JsonIgnore] public long RemainingMilliseconds => RemainingAt(Environment.TickCount64);
    public long RemainingAt(long ticks) => Math.Max(0, SavedRemainingMilliseconds - Math.Max(0, ticks - _anchor));

    public static ElapsedCountdown Start(long milliseconds, long? ticks = null)
        => new() { SavedRemainingMilliseconds = Math.Max(0, milliseconds), _anchor = ticks ?? Environment.TickCount64 };

    public void Checkpoint(long ticks)
    {
        SavedRemainingMilliseconds = RemainingAt(ticks);
        _anchor = ticks;
    }

    public void Recover(long maximum, long ticks)
    {
        // Invalid checkpoint values must not shorten a blocking interval.
        if (SavedRemainingMilliseconds < 0 || SavedRemainingMilliseconds > maximum)
            SavedRemainingMilliseconds = maximum;
        _anchor = ticks;
    }

    public static string Format(long milliseconds)
    {
        var remaining = TimeSpan.FromSeconds(Math.Ceiling(Math.Max(0, milliseconds) / 1000d));
        return remaining.Days > 0 ? $"{remaining.Days}일 {remaining:hh\\:mm\\:ss}" : remaining.ToString(@"hh\:mm\:ss");
    }
}
