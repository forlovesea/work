using System.Diagnostics;

namespace PCRemoteControl.Watchdog;
static class Program
{
    [STAThread]
    static void Main()
    {
        using var mutex = new Mutex(false, "Local\\PCRemoteControl.Watchdog");
        bool owns;
        try { owns = mutex.WaitOne(0); } catch (AbandonedMutexException) { owns = true; }
        if (!owns) return;
        try { ApplicationConfiguration.Initialize(); Application.Run(new WatchdogForm()); }
        finally { mutex.ReleaseMutex(); }
    }
}
sealed class WatchdogForm : Form
{
    readonly Label status = new() { Dock = DockStyle.Fill, Padding = new Padding(16) };
    readonly System.Windows.Forms.Timer timer = new() { Interval = 2000 };
    readonly string folder = Path.Combine(Path.GetTempPath(), "PCRemoteControl-watchdog-" + Guid.NewGuid().ToString("N"));
    readonly string log = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PCRemoteControl", "watchdog.log");
    Process? child;
    bool enabled = true;
    int failures;
    long launched, nextLaunch;
    string HealthPath => Path.Combine(folder, "health");
    public WatchdogForm()
    {
        Text = "PCRemoteControl v0.1.3 · TARGET 감시"; Size = new Size(540, 220);
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 64, Padding = new Padding(10) };
        var resume = new AppButton { Text = "감시 시작", AutoSize = true };
        var pause = new AppButton { Text = "감시 중지", AutoSize = true };
        buttons.Controls.AddRange(new Control[] { resume, pause }); Controls.Add(status); Controls.Add(buttons); DarkTheme.Apply(this); MinimumSize = new Size(540, 240);
        resume.Click += (_, _) => { enabled = true; failures = 0; nextLaunch = 0; Report("감시 시작 · TARGET의 연결 중지 상태는 TARGET에서 서버 연결로 해제하세요."); };
        pause.Click += (_, _) => { enabled = false; Report("감시 중지 · TARGET은 계속 실행됩니다."); };
        Directory.CreateDirectory(folder);
        timer.Tick += (_, _) => Check(); timer.Start();
        Shown += (_, _) => Check();
        FormClosed += (_, _) => { timer.Dispose(); child?.Dispose(); /* TARGET stays running; no restart after monitor closes. */ };
    }
    void Report(string message)
    {
        status.Text = message;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(log)!);
            if (File.Exists(log) && new FileInfo(log).Length > 512000) File.Move(log, log + ".old", true);
            File.AppendAllText(log, DateTimeOffset.Now.ToString("O") + " " + message + Environment.NewLine);
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
    void Check()
    {
        if (!enabled) return;
        try
        {
            string state = File.Exists(HealthPath) ? File.ReadAllText(HealthPath) : "";
            if (state == "stopped") { enabled = false; Report("TARGET 정상 종료 · 자동 재실행 중지. 감시 시작을 누르면 다시 실행합니다."); File.Delete(HealthPath); return; }
            if (child == null)
            {
                if (Environment.TickCount64 < nextLaunch) return;
                // Never adopt or terminate an unrelated process or a manually started TARGET.
                using var mutex = new Mutex(false, "Local\\PCRemoteControl.Target");
                bool free;
                try { free = mutex.WaitOne(0); } catch (AbandonedMutexException) { free = true; }
                if (!free) { enabled = false; Report("이미 TARGET이 실행 중입니다. 기존 TARGET을 닫고 감시 시작을 누르세요."); return; }
                mutex.ReleaseMutex();
                File.Delete(HealthPath);
                var executable = Path.Combine(AppContext.BaseDirectory, "PCRemoteControl-v0.1.3.exe");
                var info = new ProcessStartInfo(executable) { UseShellExecute = false, WorkingDirectory = AppContext.BaseDirectory };
                info.ArgumentList.Add("--target"); info.ArgumentList.Add("--auto-connect"); info.ArgumentList.Add("--watchdog-dir"); info.ArgumentList.Add(folder);
                child = Process.Start(info) ?? throw new IOException("TARGET 실행 실패");
                launched = Environment.TickCount64; Report("TARGET 실행 · 2초마다 확인, UI 무응답 60초 시 재실행"); return;
            }
            if (state == "paused")
            {
                if (child.HasExited) { child.Dispose(); child = null; enabled = false; Report("TARGET 연결 중지 상태에서 종료됨 · 감시 시작으로 재개"); File.Delete(HealthPath); }
                return;
            }
            bool stale = RecoveryPolicy.IsStale(Environment.TickCount64 - launched,
                File.Exists(HealthPath) ? (DateTime.UtcNow - File.GetLastWriteTimeUtc(HealthPath)).TotalSeconds : double.PositiveInfinity);
            if (!child.HasExited && !stale) { if (Environment.TickCount64 - launched > 300000) failures = 0; return; }
            if (!child.HasExited) { child.Kill(); if (!child.WaitForExit(3000)) return; }
            child.Dispose(); child = null;
            failures++; int delay = RecoveryPolicy.DelaySeconds(failures);
            nextLaunch = Environment.TickCount64 + delay * 1000L;
            Report($"TARGET 종료/무응답 감지 · {delay}초 후 재실행 (연속 {failures}회)");
        }
        catch (Exception ex) { nextLaunch = Environment.TickCount64 + 30000; Report("감시 오류 · " + ex.Message); }
    }
}
