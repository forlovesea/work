namespace PCRemoteControl;

static class DiagnosticLog
{
    static readonly object Gate = new();
    public static void Write(string stage, string detail)
    {
        try
        {
            lock (Gate)
            {
                string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PCRemoteControl");
                Directory.CreateDirectory(folder);
                string path = Path.Combine(folder, "client.log");
                if (File.Exists(path) && new FileInfo(path).Length > 512000) File.Move(path, path + ".old", true);
                File.AppendAllText(path, $"{DateTimeOffset.Now:O} {stage} {detail.Replace('\r', ' ').Replace('\n', ' ')}{Environment.NewLine}");
            }
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
