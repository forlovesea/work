using SafeChild;
using System.Text.Json;

internal static class WeeklyChecks
{
    public static void Run(Action<bool, string> check)
    {
        var schedule = new DomainSchedule { Enabled = true, Type = DomainTimeType.Weekly };
        // 2026-09-07 is Monday. Use local dates so the test follows the same PC clock as the app.
        DateTime At(int day, int hour, int minute = 0) => new(2026, 9, day, hour, minute, 0, DateTimeKind.Local);
        bool Active(int day, int hour, int minute = 0) => schedule.Includes(new DateTimeOffset(At(day, hour, minute)));
        check(!Active(7, 17, 59) && Active(7, 18) && !Active(7, 22), "Weekday start inclusive / end exclusive");
        check(!Active(12, 8, 59) && Active(12, 9) && !Active(12, 21), "Saturday uses weekend hours");
        check(Active(13, 10) && !Active(14, 10), "Sunday weekend / Monday weekday");
        check(schedule.GetWeeklyState(At(7, 17)).NextChange == At(7, 18), "Next weekday start");
        check(schedule.GetWeeklyState(At(11, 23)).NextChange == At(12, 9), "Friday to Saturday next start");
        schedule.Weekdays.Start = TimeSpan.FromHours(22); schedule.Weekdays.End = TimeSpan.FromHours(7);
        check(Active(12, 6, 59) && !Active(12, 7), "Friday overnight extends into Saturday");
        schedule.Weekends.Start = TimeSpan.FromHours(6);
        check(schedule.GetWeeklyState(At(12, 5)).NextChange == At(12, 21), "Overlapping Friday/Saturday windows merge");
        schedule.Weekends.Start = TimeSpan.FromHours(7);
        check(schedule.GetWeeklyState(At(12, 5)).NextChange == At(12, 21), "Touching windows have no temporary release");
        schedule.Weekends.Enabled = false;
        check(Active(12, 6) && !Active(12, 23), "Disabled weekend retains Friday spillover only");
        check(schedule.GetWeeklyState(At(13, 9)).NextChange == At(14, 22), "Disabled weekend waits for Monday");
        schedule.Weekdays.Enabled = false;
        check(!Active(7, 23) && schedule.GetWeeklyState(At(7, 23)).NextChange is null, "Both groups disabled");
        schedule.Enabled = false;
        check(Active(7, 23), "Time checkbox disabled keeps manual block");
        schedule.Enabled = true; schedule.Weekdays.Enabled = true; schedule.Weekends.Enabled = true;
        schedule.Weekdays.Start = schedule.Weekdays.End = TimeSpan.Zero;
        schedule.Weekends.Start = schedule.Weekends.End = TimeSpan.Zero;
        check(Active(7, 0) && Active(13, 23, 59) && schedule.GetWeeklyState(At(7, 12)).NextChange is null, "All-day continuous weekly block");
        schedule.Weekends.Enabled = false;
        check(schedule.GetWeeklyState(At(11, 23)).NextChange == At(12, 0), "All-day weekdays release at Saturday midnight");
        schedule.Weekdays.Start = TimeSpan.FromHours(18); schedule.Weekdays.End = TimeSpan.FromHours(22);
        var domain = new BlockEntry { Schedule = schedule };
        var port = new PortEntry { Port = 443, Schedule = schedule };
        var before = new DateTimeOffset(At(7, 17));
        check(domain.GetRemainingTime(before) == "시작까지 01:00:00", "Repeating remaining time before start");
        check(port.GetRemainingTime(new DateTimeOffset(At(7, 19))) == "해제까지 03:00:00", "Port repeating remaining time during block");
        check(domain.ShouldBlock(before) == port.ShouldBlock(before), "Domain and port share weekly policy");
        domain.Active = false;
        check(!domain.ShouldBlock(new DateTimeOffset(At(7, 19))), "Manual release overrides weekly schedule");
        var restored = JsonSerializer.Deserialize<DomainSchedule>(JsonSerializer.Serialize(schedule))!;
        check(restored.Weekdays.Start == schedule.Weekdays.Start && !restored.Weekends.Enabled && restored.Type == DomainTimeType.Weekly, "Weekly settings survive JSON reload");
        check((int)DomainTimeType.Absolute == 0 && (int)DomainTimeType.Walltime == 1, "Existing saved type IDs remain compatible");
    }
}
