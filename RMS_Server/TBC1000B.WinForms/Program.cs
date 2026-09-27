namespace TBC1000B.WinForms;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        // Resolve command-line paths before anchoring portable data to the executable.
        if (args.Length >= 2 && args[0] == "--profile") args[1] = Path.GetFullPath(args[1]);
        // With full bundle extraction, BaseDirectory points at the runtime cache.
        // Keep customer settings and records next to the original executable.
        Environment.CurrentDirectory = Path.GetDirectoryName(Environment.ProcessPath) ?? AppContext.BaseDirectory;
        ApplicationConfiguration.Initialize();
#if DEBUG
        Snmp.SnmpCodecSelfTest.Run();
#endif
        var profileDirectory = Path.Combine(Environment.CurrentDirectory, "profiles");
        Directory.CreateDirectory(profileDirectory);
        using var instanceLock = TryAcquireInstanceLock(Path.Combine(Environment.CurrentDirectory, "app.lock"));
        var masterProfileFile = Path.Combine(profileDirectory, "master_profile.txt");
        if (instanceLock is not null)
        {
            try { File.Delete(masterProfileFile); } catch (IOException) { } catch (UnauthorizedAccessException) { }
        }
        var masterRunning = File.Exists(masterProfileFile);
        if (args.Length >= 2 && args[0] == "--profile")
        {
            var path = Path.GetFullPath(args[1]);
            if (!File.Exists(path)) { MessageBox.Show($"프로파일 파일이 없습니다.\n{path}", "실행 오류", MessageBoxButtons.OK, MessageBoxIcon.Error); return; }
            var loaded = new Services.ProfileStore(Path.GetDirectoryName(path)!).Load(path);
            var mode = args.Skip(2).FirstOrDefault(a => a is "Master" or "Slave") ?? "Master";
            if (masterRunning && mode == "Master") mode = "Slave";
            Application.Run(new Views.MainForm(mode, loaded)); return;
        }
        using var profile = new Views.ProfileDialog(profileDirectory, masterRunning);
        if (profile.ShowDialog() != DialogResult.OK) return;
        Application.Run(new Views.MainForm(profile.SelectedMode, profile.SelectedProfile));
    }

    private static FileStream? TryAcquireInstanceLock(string path)
    {
        try { return new FileStream(path, FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None, 1, FileOptions.DeleteOnClose); }
        catch (IOException) { return null; }
        catch (UnauthorizedAccessException) { return null; }
    }
}
