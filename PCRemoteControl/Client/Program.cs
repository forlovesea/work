namespace PCRemoteControl;
static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        bool target = args.Contains("--target");
        using var singleTarget = new Mutex(false, "Local\\PCRemoteControl.Target");
        bool owns = false;
        if (target)
        {
            try { owns = singleTarget.WaitOne(0); } catch (AbandonedMutexException) { owns = true; }
            if (!owns) return;
        }
        try
        {
            int index = Array.IndexOf(args, "--watchdog-dir");
            string? folder = index >= 0 && index + 1 < args.Length ? args[index + 1] : null;
            Application.Run(new MainForm(target, args.Contains("--auto-connect"), folder));
        }
        finally { if (owns) singleTarget.ReleaseMutex(); }
    }
}
