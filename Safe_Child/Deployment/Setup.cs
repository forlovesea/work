using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;

internal static class Setup
{
    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        using (var form = new Form())
        {
            form.Text = "SafeChild Setup";
            form.ClientSize = new System.Drawing.Size(480, 130);
            form.StartPosition = FormStartPosition.CenterScreen;
            form.FormBorderStyle = FormBorderStyle.FixedDialog;
            form.MaximizeBox = false;
            form.MinimizeBox = false;
            var label = new Label { Text = "설치 파일을 준비하고 있습니다…", AutoSize = true, Left = 24, Top = 24 };
            form.Controls.Add(label);
            form.Controls.Add(new ProgressBar { Left = 24, Top = 65, Width = 430, Style = ProgressBarStyle.Marquee });
            var complete = false;
            form.FormClosing += delegate(object sender, FormClosingEventArgs e) { e.Cancel = !complete; };
            form.Shown += async delegate
            {
                var stage = Path.Combine(Path.GetTempPath(), "SafeChild-Package-" + Guid.NewGuid().ToString("N"));
                try
                {
                    if (!Environment.Is64BitOperatingSystem) throw new InvalidOperationException("Windows 10/11 64비트가 필요합니다.");
                    Directory.CreateDirectory(stage);
                    await Task.Run(delegate
                    {
                        foreach (var name in new[] { "Payload.zip", "Install.ps1" })
                        {
                            using (var source = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
                            using (var target = File.Create(Path.Combine(stage, name)))
                            {
                                if (source == null) throw new InvalidOperationException("설치 파일이 손상되었습니다.");
                                source.CopyTo(target);
                            }
                        }
                    });
                    label.Text = "SafeChild를 설치하고 있습니다…";
                    var info = new ProcessStartInfo("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File \"" + Path.Combine(stage, "Install.ps1") + "\"")
                    { UseShellExecute = false, CreateNoWindow = true };
                    using (var process = Process.Start(info))
                    {
                        await Task.Run(delegate { process.WaitForExit(); });
                        Environment.ExitCode = process.ExitCode;
                    }
                }
                catch (Exception ex)
                {
                    Environment.ExitCode = 1;
                    MessageBox.Show(form, ex.Message, "SafeChild 설치 오류", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
                finally
                {
                    var resolved = Path.GetFullPath(stage);
                    var temp = Path.GetFullPath(Path.GetTempPath()).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                    if (resolved.StartsWith(temp, StringComparison.OrdinalIgnoreCase) && Path.GetFileName(resolved).StartsWith("SafeChild-Package-"))
                    {
                        try { Directory.Delete(resolved, true); } catch { }
                    }
                    complete = true;
                    form.Close();
                }
            };
            Application.Run(form);
        }
    }
}
