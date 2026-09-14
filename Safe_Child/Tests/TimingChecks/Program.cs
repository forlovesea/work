using SafeChild;
using System.Text.Json;

var checks = 0;
void Check(bool passed, string name)
{
    if (!passed) throw new Exception(name);
    checks++; Console.WriteLine("PASS: " + name);
}
var timer = ElapsedCountdown.Start(60000, 1000);
Check(timer.RemainingAt(11000) == 50000, "Monotonic elapsed duration");
Check(timer.RemainingAt(61000) == 0 && timer.RemainingAt(90000) == 0, "Expiry never negative");
timer.Checkpoint(11000);
var recovered = JsonSerializer.Deserialize<ElapsedCountdown>(JsonSerializer.Serialize(timer))!;
recovered.Recover(60000, 200); // New boot: uptime has reset.
Check(recovered.RemainingAt(200) == 50000, "New boot preserves checkpoint without calendar credit");
Check(recovered.RemainingAt(10200) == 40000, "Countdown continues after recovery");
recovered.Recover(60000, 5000000);
Check(recovered.RemainingAt(5000000) == 50000, "Restart cannot claim downtime by advancing uptime");
var invalid = ElapsedCountdown.Start(60000); invalid.SavedRemainingMilliseconds = -1;
invalid.Recover(60000, 10);
Check(invalid.RemainingAt(10) == 60000, "Negative checkpoint restores full blocking interval");
invalid.SavedRemainingMilliseconds = long.MaxValue; invalid.Recover(60000, 10);
Check(invalid.RemainingAt(10) == 60000, "Out of range checkpoint is bounded");
var expired = ElapsedCountdown.Start(0); expired.Recover(60000, 10);
Check(expired.RemainingAt(10) == 0, "Valid completed countdown remains completed");
var settings = new AppSettings { AllowAllUntil = DateTimeOffset.UtcNow.AddYears(10), AllowAllCountdown = ElapsedCountdown.Start(60000) };
var block = new BlockEntry { Schedule = new() { Enabled = true, Type = DomainTimeType.Walltime, WalltimeMinutes = 1, Countdown = ElapsedCountdown.Start(60000) } };
settings.Domains.Add(block);
Check(block.ShouldBlock(DateTimeOffset.UtcNow.AddYears(-10)) && block.ShouldBlock(DateTimeOffset.UtcNow.AddYears(10)), "PC clock changes cannot disable running Walltime");
Check(settings.IsAllowAllActive(DateTimeOffset.MinValue) && settings.IsAllowAllActive(DateTimeOffset.MaxValue), "Allowance ignores calendar adjustments");
settings.AllowAllCountdown = ElapsedCountdown.Start(0);
Check(!settings.IsAllowAllActive(DateTimeOffset.MinValue), "Clock rewind cannot revive expired allowance");
settings.AllowAllCountdown = ElapsedCountdown.Start(60000);
settings.CheckpointTimers(Environment.TickCount64);
var restored = JsonSerializer.Deserialize<AppSettings>(JsonSerializer.Serialize(settings))!;
restored.RecoverTimers(Environment.TickCount64);
Check(restored.AllowAllCountdown is null && restored.AllowAllUntil is null, "Restart revokes permissive override");
Check(restored.Domains[0].ShouldBlock(DateTimeOffset.UtcNow.AddYears(10)), "Restart retains domain protection despite future PC clock");
var legacy = JsonSerializer.Deserialize<AppSettings>("{\"Domains\":[{\"Domain\":\"example.com\",\"Schedule\":{\"Enabled\":true,\"Type\":1,\"WalltimeMinutes\":30}}]}")!;
legacy.RecoverTimers(Environment.TickCount64);
Check(legacy.Domains[0].Schedule.Countdown!.RemainingMilliseconds > 1799000, "Legacy Walltime migrates conservatively");
block.Schedule.Countdown = ElapsedCountdown.Start(0);
Check(!block.ShouldBlock(DateTimeOffset.UtcNow.AddYears(-10)), "Expired Walltime stays expired after clock rewind");
block.Active = false;
Check(!block.ShouldBlock(DateTimeOffset.UtcNow), "Manual domain disable still works");
block.Active = true; block.Schedule.Enabled = false;
Check(block.ShouldBlock(DateTimeOffset.UtcNow), "Time checkbox off retains manual blocking");
var now = DateTimeOffset.UtcNow;
block.Schedule = new() { Enabled = true, Start = now, End = now.AddMinutes(1) };
Check(!block.ShouldBlock(now.AddSeconds(-1)) && block.ShouldBlock(now) && !block.ShouldBlock(now.AddMinutes(1)), "Absolute scheduling is unchanged");
Check(ElapsedCountdown.Format(100) == "00:00:01" && ElapsedCountdown.Format(86400000) == "1일 00:00:00", "Remaining time display");
var legacyPort = JsonSerializer.Deserialize<PortEntry>("{\"Port\":443,\"Protocol\":\"TCP\",\"Active\":true}")!;
Check(legacyPort.ShouldBlock(now) && !legacyPort.TimeEnabled, "Existing port rules retain manual blocking");
var port = new PortEntry { Port = 443, Protocol = "UDP", Schedule = new() { Enabled = true, Start = now, End = now.AddMinutes(1) } };
Check(port.ShouldBlock(now) && !port.ShouldBlock(now.AddMinutes(1)), "Port absolute schedule start and expiry");
port.Schedule = new() { Enabled = true, Type = DomainTimeType.Walltime, WalltimeMinutes = 1, Countdown = ElapsedCountdown.Start(60000) };
Check(port.ShouldBlock(now.AddYears(-10)) && port.ShouldBlock(now.AddYears(10)), "Port Walltime ignores clock manipulation");
var portSettings = new AppSettings { Ports = [port] };
portSettings.CheckpointTimers(Environment.TickCount64);
var portRecovery = JsonSerializer.Deserialize<AppSettings>(JsonSerializer.Serialize(portSettings))!;
portRecovery.RecoverTimers(Environment.TickCount64);
Check(portRecovery.Ports[0].Schedule.Countdown!.RemainingMilliseconds > 59000 && portRecovery.Ports[0].Protocol == "UDP", "Port countdown and protocol survive restart");
port.Schedule.Countdown = ElapsedCountdown.Start(0);
Check(!port.ShouldBlock(now) && port.RemainingTime == "만료", "Expired port countdown permits traffic");
port.Schedule.Enabled = false;
Check(port.ShouldBlock(now), "Port time checkbox off restores manual blocking");
port.Active = false;
Check(!port.ShouldBlock(now), "Manual port disable takes effect");
var beforeReset = new AppSettings
{
    PasswordSalt = "existing-salt", PasswordHash = "existing-hash",
    Domains = [new() { Domain = "example.com", Schedule = new() { Enabled = true } }],
    Ports = [new() { Port = 443, Protocol = "TCP" }],
    AllowAllUntil = DateTimeOffset.UtcNow.AddHours(1), AllowAllCountdown = ElapsedCountdown.Start(3600000),
    LastCheckpointUtc = DateTimeOffset.UtcNow
};
var reset = beforeReset.ResetKeepingPassword();
Check(reset.PasswordSalt == beforeReset.PasswordSalt && reset.PasswordHash == beforeReset.PasswordHash, "Settings reset preserves administrator credentials");
Check(reset.Domains.Count == 0 && reset.Ports.Count == 0, "Settings reset removes domain and port schedules");
Check(reset.AllowAllUntil is null && reset.AllowAllCountdown is null && reset.LastCheckpointUtc is null, "Settings reset clears allowance and timing state");
Check(beforeReset.Domains.Count == 1 && beforeReset.Ports.Count == 1, "Previous settings remain available for save failure rollback");
var range = new PortEntry { Port = 8000, EndPort = 9000, Protocol = "TCP" };
range.ValidateRange();
Check(range.PortRange == "8000-9000", "Firewall port range syntax");
var rangeReloaded = JsonSerializer.Deserialize<PortEntry>(JsonSerializer.Serialize(range))!;
Check(rangeReloaded.Port == 8000 && rangeReloaded.EffectiveEndPort == 9000, "Port range persists");
Check(new PortEntry { Port = 443 }.PortRange == "443", "Legacy single port remains supported");
Check(new PortEntry { Port = 443, EndPort = 443 }.PortRange == "443", "Equal range endpoints normalize to single port");
new PortEntry { Port = 1, EndPort = 65535 }.ValidateRange();
Check(true, "Full valid port range accepted");
foreach (var invalidRange in new[] { new PortEntry { Port = 9000, EndPort = 8000 }, new PortEntry { Port = 0 }, new PortEntry { Port = 1, EndPort = 65536 } })
{
    var rejected = false;
    try { invalidRange.ValidateRange(); } catch (ArgumentException) { rejected = true; }
    Check(rejected, "Invalid or reversed port range rejected");
}
WeeklyChecks.Run(Check);
Console.WriteLine($"{checks} checks passed");
