namespace PCRemoteControl.Watchdog;
static class RecoveryPolicy
{
    public static int DelaySeconds(int failures) => Math.Min(60, 5 * (1 << Math.Clamp(failures - 1, 0, 4)));
    public static bool IsStale(long ageMilliseconds, double heartbeatAgeSeconds) => ageMilliseconds > 60000 && heartbeatAgeSeconds > 60;
}
