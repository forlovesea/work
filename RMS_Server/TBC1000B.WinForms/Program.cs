namespace TBC1000B.WinForms;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
#if DEBUG
        Snmp.SnmpCodecSelfTest.Run();
#endif
        if (args.Length >= 2 && args[0] == "--profile")
        {
            var path = Path.GetFullPath(args[1]);
            if (!File.Exists(path)) { MessageBox.Show($"프로파일 파일이 없습니다.\n{path}", "실행 오류", MessageBoxButtons.OK, MessageBoxIcon.Error); return; }
            var loaded = new Services.ProfileStore(Path.GetDirectoryName(path)!).Load(path);
            var mode = args.Skip(2).FirstOrDefault(a => a is "Master" or "Slave") ?? "Master";
            Application.Run(new Views.MainForm(mode, loaded)); return;
        }
        using var profile = new Views.ProfileDialog();
        if (profile.ShowDialog() != DialogResult.OK) return;
        Application.Run(new Views.MainForm(profile.SelectedMode, profile.SelectedProfile));
    }
}
