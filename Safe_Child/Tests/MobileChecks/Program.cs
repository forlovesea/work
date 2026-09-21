using SafeChild;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

var count = 0;
void Check(bool value, string name) { if (!value) throw new Exception(name); Console.WriteLine("PASS: " + name); count++; }
void Reject(Action action, int status, string name)
{
    try { action(); throw new Exception("Expected rejection: " + name); }
    catch (MobileRuleException ex) { Check(ex.Status == status, name); }
}
string Normalize(string value) => new Uri(value.Contains("://") ? value : "https://" + value).IdnHost.ToLowerInvariant();
var settings = new AppSettings();
var schedule = MobileRules.ScheduleView(new DomainSchedule { Enabled = true, Type = DomainTimeType.Weekly });
var add = new MobileRuleCommand("save", null, null, "example.com", true, schedule);
MobileRules.Execute(settings, add, Normalize, () => { });
Check(settings.Domains.Count == 1, "Add rule");
var entry = settings.Domains[0]; entry.ChildMessage = "Preserve this message";
var version = MobileRules.Version(entry);
var command = add with { OriginalDomain = entry.Domain, Version = version, Active = false };
MobileRules.Execute(settings, command, Normalize, () => { });
Check(!settings.Domains[0].Active && settings.Domains[0].ChildMessage == entry.ChildMessage, "Edit keeps child message and changes active state");
Reject(() => MobileRules.Execute(settings, command, Normalize, () => { }), 409, "Stale editor rejected");
Reject(() => MobileRules.Execute(settings, add, Normalize, () => { }), 409, "Duplicate rejected");
var previous = settings.Domains;
try { MobileRules.Execute(settings, add with { Domain = "other.example.com" }, Normalize, () => throw new IOException("disk full")); }
catch (IOException) { }
Check(ReferenceEquals(previous, settings.Domains) && settings.Domains.Count == 1, "Save failure rolls back rule collection");
Reject(() => MobileRules.BuildSchedule(schedule with { Days = [] }, null), 400, "Missing days rejected");
var badDays = schedule.Days.ToArray(); badDays[0] = new(true, "25:00", "07:00");
Reject(() => MobileRules.BuildSchedule(schedule with { Days = badDays }, null), 400, "Invalid clock rejected");
Reject(() => MobileRules.BuildSchedule(schedule with { Type = 0, End = schedule.Start }, null), 400, "Invalid absolute range rejected");
Reject(() => MobileRules.BuildSchedule(schedule with { Minutes = 0 }, null), 400, "Invalid duration rejected");
var timer = MobileRules.BuildSchedule(schedule with { Type = 1, Minutes = 60 }, null);
var timerVersionEntry = new BlockEntry { Domain = "timer.example.com", Schedule = timer };
var timerVersion = MobileRules.Version(timerVersionEntry);
timer.Countdown!.Checkpoint(Environment.TickCount64);
Check(timerVersion == MobileRules.Version(timerVersionEntry), "Timer checkpoints do not conflict with editing");
var kept = MobileRules.BuildSchedule(MobileRules.ScheduleView(timer), timer);
Check(ReferenceEquals(timer.Countdown, kept.Countdown), "Unchanged duration preserves elapsed timer");
var restarted = MobileRules.BuildSchedule(MobileRules.ScheduleView(timer) with { Restart = true }, timer);
Check(!ReferenceEquals(timer.Countdown, restarted.Countdown), "Explicit restart creates new timer");
var days = Enumerable.Range(0, 7).Select(_ => new MobileWindow(false, "00:00", "00:00")).ToArray();
days[5] = new(true, "22:00", "07:00");
var weekly = MobileRules.BuildSchedule(schedule with { Days = days }, null);
DateTime At(int day, int hour) => new(2026, 9, day, hour, 0, 0);
Check(weekly.GetWeeklyState(At(12, 6)).Active && !weekly.GetWeeklyState(At(12, 7)).Active, "Friday overnight into disabled Saturday");
days[6] = new(true, "07:00", "12:00"); weekly = MobileRules.BuildSchedule(schedule with { Days = days }, null);
Check(weekly.GetWeeklyState(At(12, 6)).NextChange == At(12, 12), "Adjacent daily windows merge");
days[0] = new(true, "22:00", "07:00"); weekly = MobileRules.BuildSchedule(schedule with { Days = days }, null);
Check(weekly.GetWeeklyState(At(14, 6)).Active && weekly.GetWeeklyState(At(14, 6)).NextChange == At(14, 7), "Sunday wraps into Monday");
var restored = JsonSerializer.Deserialize<DomainSchedule>(JsonSerializer.Serialize(weekly))!;
Check(restored.Days is { Length: 7 } && restored.GetWeeklyState(At(14, 6)).Active, "Daily rules survive persistence");
foreach (var d in days.Select((_, i) => i).ToArray()) days[d] = new(true, "18:00", "18:00");
weekly = MobileRules.BuildSchedule(schedule with { Days = days }, null);
Check(weekly.GetWeeklyState(At(14, 6)) == new WeeklyScheduleState(true, null), "Seven full days stay continuous");
var snapshot = MobileRules.Read(settings);
Check(!JsonSerializer.Serialize(snapshot).Contains("Password") && !JsonSerializer.Serialize(snapshot).Contains("Countdown"), "API excludes credentials and timer internals");
settings.AllowAllCountdown = ElapsedCountdown.Start(60000);
var allowance = settings.AllowAllCountdown;
var allowedRule = MobileRules.Read(settings).Rules[0];
MobileRules.Execute(settings, command with { Version = allowedRule.Version, Active = true }, Normalize, () => { });
Check(ReferenceEquals(allowance, settings.AllowAllCountdown) && MobileRules.Read(settings).Rules[0].State == "전체 일시 허용 중",
    "Editing rules preserves global allowance and reports effective state");
settings.AllowAllCountdown = null;
Check(MobileRules.Read(settings, "apply failed").Rules[0].State == "적용 확인 필요", "Apply failure never reports confirmed block");
settings.Domains[0].Active = false;

var listener = new System.Net.Sockets.TcpListener(IPAddress.Loopback, 0); listener.Start();
var port = ((IPEndPoint)listener.LocalEndpoint).Port; listener.Stop();
await using var server = new MobileControlServer(p => Task.FromResult(p == "test-parent-password"),
    _ => Task.FromResult(new MobileStatus(false, null, 0, null)),
    input => { if (input is not null) MobileRules.Execute(settings, input, Normalize, () => { }); return Task.FromResult(MobileRules.Read(settings)); });
await server.StartAsync(new LanAddress("test", IPAddress.Loopback, IPAddress.Parse("255.0.0.0")), port);
using var handler = new HttpClientHandler { ServerCertificateCustomValidationCallback = (_, _, _, _) => true, UseProxy = false };
using var client = new HttpClient(handler) { BaseAddress = new Uri(server.Url + "/") };
client.DefaultRequestHeaders.Add("Origin", new Uri(server.Url!).GetLeftPart(UriPartial.Authority));
client.DefaultRequestHeaders.Add("X-SafeChild", "1");
Check((await client.GetAsync("api/rules")).StatusCode == HttpStatusCode.Unauthorized, "Rules require authentication");
Check((await client.PostAsJsonAsync("api/rules", add)).StatusCode == HttpStatusCode.Unauthorized, "Writes require authentication");
Check((await client.GetAsync("")).IsSuccessStatusCode, "Embedded mobile page served");
Check((await client.PostAsJsonAsync("api/login", new { password = "wrong" })).StatusCode == HttpStatusCode.Unauthorized, "Wrong password rejected");
Check((await client.PostAsJsonAsync("api/login", new { password = "test-parent-password" })).IsSuccessStatusCode, "Login succeeds");
var response = await client.GetFromJsonAsync<MobileRulesResult>("api/rules");
Check(response!.Rules.Length == 1, "Authenticated rule listing");
client.DefaultRequestHeaders.Remove("Origin"); client.DefaultRequestHeaders.Add("Origin", "https://untrusted.example");
Check((await client.PostAsJsonAsync("api/rules", add)).StatusCode == HttpStatusCode.Forbidden, "Cross-origin writes rejected");
client.DefaultRequestHeaders.Remove("Origin"); client.DefaultRequestHeaders.Add("Origin", new Uri(server.Url!).GetLeftPart(UriPartial.Authority));
Check((await client.PostAsJsonAsync("api/rules", add with { Domain = "second.example.com" })).IsSuccessStatusCode, "Authenticated addition");
var update = MobileRules.Read(settings).Rules.Single(r => r.Domain == "second.example.com");
Check((await client.PostAsJsonAsync("api/rules", new MobileRuleCommand("save", update.Domain, update.Version,
    "renamed.example.com", false, update.Schedule))).IsSuccessStatusCode, "Authenticated rename and deactivation");
Check((await client.PostAsJsonAsync("api/rules", command)).StatusCode == HttpStatusCode.Conflict, "HTTP stale version conflict");
Check((await client.PostAsJsonAsync("api/rules", add with { Domain = "invalid.example.com", Schedule = schedule with { Minutes = -1 } })).StatusCode == HttpStatusCode.BadRequest, "HTTP invalid input rejected");
var rule = MobileRules.Read(settings).Rules[0];
Check((await client.PostAsJsonAsync("api/rules", new MobileRuleCommand("delete", rule.Domain, rule.Version, null, false, null))).IsSuccessStatusCode, "Authenticated deletion");
Check(settings.Domains.Count == 1 && settings.Domains[0].Domain == "renamed.example.com", "Deletion targets correct domain");
await client.PostAsJsonAsync("api/logout", new { });
Check((await client.GetAsync("api/rules")).StatusCode == HttpStatusCode.Unauthorized, "Logout revokes access");
await ExternalChecks.Run(Check);
Console.WriteLine($"{count} mobile checks passed.");
