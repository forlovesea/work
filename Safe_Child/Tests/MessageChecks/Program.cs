using SafeChild;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

internal static class Program
{
    private static int checks;
    private static void Check(bool condition, string name) { if (!condition) throw new Exception(name); checks++; }

    [STAThread]
    private static void Main()
    {
        var startupScript = AutoStartService.BuildScript(@"C:\Program Files\SafeChild's Test\SafeChild.exe", "S-1-5-21-1-2-3-1001", true);
        Check(startupScript.Contains("SafeChild''s Test"), "startup executable quoted safely");
        Check(startupScript.Contains("-LogonType Interactive -RunLevel Highest"), "startup interactive elevated user");
        Check(startupScript.Contains("-ExecutionTimeLimit ([TimeSpan]::Zero)"), "startup no three-day timeout");
        Check(!startupScript.Contains("-Password"), "startup no password storage");
        Check(AutoStartService.BuildScript("unused", "S-1-5-21-1-2-3-1001", false).Contains("Unregister-ScheduledTask"), "startup reset removal");
        File.WriteAllText(Path.Combine(AppContext.BaseDirectory, "AutoStart.check.ps1"), startupScript);
        var settings = new AppSettings { Domains = [new() { Domain = "example.com", ChildMessage = "우리 잠깐 쉬어갈까요?\n사랑해요 & 응원해요." }] };
        var now = DateTimeOffset.UtcNow;
        Check(ChildMessagePolicy.Resolve(settings, "https://example.com/a", now)?.Message.Contains('\n') == true, "message lines");
        Check(ChildMessagePolicy.Resolve(settings, "https://www.example.com/", now) != null, "www");
        Check(ChildMessagePolicy.Resolve(settings, "https://example.com.evil.test/", now) == null, "suffix rejection");
        Check(ChildMessagePolicy.Resolve(settings, "https://example.com@evil.test/", now) == null, "userinfo rejection");
        settings.Domains[0].Active = false;
        Check(ChildMessagePolicy.Resolve(settings, "https://example.com", now) == null, "inactive");
        settings.Domains[0].Active = true;
        settings.AllowAllCountdown = ElapsedCountdown.Start(60000);
        Check(ChildMessagePolicy.Domains(settings, now).Length == 0, "allow all filters");
        Check(ChildMessagePolicy.Resolve(settings, "https://example.com", now) == null, "allow all notice");
        settings.AllowAllCountdown = null;
        var copy = JsonSerializer.Deserialize<AppSettings>(JsonSerializer.Serialize(settings))!;
        Check(copy.Domains[0].ChildMessage == settings.Domains[0].ChildMessage, "persistence roundtrip");
        settings.Domains[0].ChildMessage = "";
        Check(ChildMessagePolicy.Domains(settings, now).Length == 0, "empty message");
        Check(settings.ResetKeepingPassword().Domains.Count == 0, "reset clears messages");
        using (var popup = new ChildMessagePopup("example.com", new string('가', 2000)))
        {
            popup.CreateControl(); popup.PerformLayout();
            Check(popup.AcceptButton is Button { Text: "알겠어요" }, "dismiss button");
            popup.Display("next.example", "새 메시지");
            Check(popup.TopMost, "popup visible above browser");
        }
        SynchronizationContext.SetSynchronizationContext(null);
        MainForm.CheckEditor();
        using (var dialog = new DomainScheduleDialog("daily.example.com", new DomainSchedule
        {
            Enabled = true, Type = DomainTimeType.Weekly,
            Days = Enumerable.Range(0, 7).Select(i => new DailyBlockWindow
                { Enabled = i == 1, Start = TimeSpan.FromHours(20), End = TimeSpan.FromHours(7) }).ToArray()
        }))
        {
            var flags = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;
            dialog.CreateControl(); dialog.PerformLayout();
            var individual = (CheckBox)typeof(DomainScheduleDialog).GetField("_individual", flags)!.GetValue(dialog)!;
            Check(individual.Checked, "daily mode restored from mobile settings");
            typeof(DomainScheduleDialog).GetMethod("SaveSchedule", flags)!.Invoke(dialog, null);
            Check(dialog.Result?.Days is { Length: 7 } days && days[1].Enabled && !days[0].Enabled &&
                days[1].Start == TimeSpan.FromHours(20) && days[1].End == TimeSpan.FromHours(7), "desktop preserves mobile daily schedule");
        }
        using (var dialog = new DomainScheduleDialog("example.com", new DomainSchedule { Enabled = true, Type = DomainTimeType.Weekly }))
        {
            var flags = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;
            var type = (ComboBox)typeof(DomainScheduleDialog).GetField("_type", flags)!.GetValue(dialog)!;
            Check(type.Items.Count == 3 && type.SelectedIndex == 2, "weekly type restored in dialog");
            var weekend = (CheckBox)typeof(DomainScheduleDialog).GetField("_weekendEnabled", flags)!.GetValue(dialog)!;
            weekend.Checked = false;
            var weekendStart = (DateTimePicker)typeof(DomainScheduleDialog).GetField("_weekendStart", flags)!.GetValue(dialog)!;
            Check(!weekendStart.Enabled, "disabled weekend disables time editor");
            typeof(DomainScheduleDialog).GetMethod("SaveSchedule", flags)!.Invoke(dialog, null);
            Check(dialog.Result is { Type: DomainTimeType.Weekly, Weekends.Enabled: false } && dialog.Result.Weekdays.Start == TimeSpan.FromHours(18), "weekly dialog saves independent groups");
        }
        SynchronizationContext.SetSynchronizationContext(null);
        ServerChecks().GetAwaiter().GetResult();
        Console.WriteLine($"{checks} message checks passed.");
    }

    private static async Task ServerChecks()
    {
        const int port = 47839;
        var visit = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
        await using var server = new BrowserMessageServer(() => Task.FromResult(new[] { "example.com" }), url => { visit.TrySetResult(url); return Task.CompletedTask; });
        await server.StartAsync(port);
        using var http = new HttpClient();
        Check((await http.GetAsync($"http://127.0.0.1:{port}/browser")).StatusCode == HttpStatusCode.Forbidden, "foreign origin refused");
        using var socket = new ClientWebSocket();
        socket.Options.SetRequestHeader("Origin", $"chrome-extension://{BrowserMessageServer.ExtensionId}");
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(8));
        await socket.ConnectAsync(new Uri($"ws://127.0.0.1:{port}/browser"), timeout.Token);
        var buffer = new byte[4096];
        var received = await socket.ReceiveAsync(buffer.AsMemory(), timeout.Token);
        Check(Encoding.UTF8.GetString(buffer, 0, received.Count).Contains("example.com"), "policy broadcast");
        await socket.SendAsync(Encoding.UTF8.GetBytes("{\"url\":\"https://example.com\"}").AsMemory(), WebSocketMessageType.Text, true, timeout.Token);
        Check(await visit.Task.WaitAsync(timeout.Token) == "https://example.com", "visit delivered");
        Check(server.ClientCount == 1, "connection count");
        socket.Abort();
        var pendingUi = new TaskCompletionSource<string[]>(TaskCreationOptions.RunContinuationsAsynchronously);
        await using var waitingServer = new BrowserMessageServer(() => pendingUi.Task, _ => Task.CompletedTask);
        await waitingServer.StartAsync(port + 1);
        using var waitingSocket = new ClientWebSocket();
        waitingSocket.Options.SetRequestHeader("Origin", $"chrome-extension://{BrowserMessageServer.ExtensionId}");
        await waitingSocket.ConnectAsync(new Uri($"ws://127.0.0.1:{port + 1}/browser"), timeout.Token);
        await waitingServer.DisposeAsync().AsTask().WaitAsync(TimeSpan.FromSeconds(5));
        Check(waitingServer.ClientCount == 0, "shutdown cancels pending UI callback with browser connected");
    }
}
