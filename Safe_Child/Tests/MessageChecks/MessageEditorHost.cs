using System.Reflection;
using System.Runtime.CompilerServices;

namespace SafeChild;

// Runs the production message page without starting history collection or changing PC protection.
public sealed partial class MainForm : Form
{
    private readonly SettingsStore _store = (SettingsStore)RuntimeHelpers.GetUninitializedObject(typeof(SettingsStore));
    private bool _adminUnlocked = true;
    private Task<T> OnUiAsync<T>(Func<T> action) => Task.FromResult(action());
    private void StyleDomainAction(Button button, Color background, Color foreground, Color border)
    {
        button.Padding = new Padding(10, 6, 10, 6);
        button.MinimumSize = new Size(0, 36);
    }

    public static void CheckEditor()
    {
        using var host = new MainForm { ClientSize = new Size(1000, 600), Font = new Font("맑은 고딕", 9F) };
        var settings = new AppSettings();
        typeof(SettingsStore).GetField("<Settings>k__BackingField", BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(host._store, settings);
        var tabs = new TabControl { Dock = DockStyle.Fill };
        host.Controls.Add(tabs);
        host._messagesPage = host.BuildMessagesTab();
        tabs.TabPages.Add(host._messagesPage);
        host.CreateControl(); tabs.CreateControl(); host._messagesPage.CreateControl();
        host.PerformLayout(); host._messagesPage.PerformLayout();
        if (!host._messageEditor.ReadOnly) throw new Exception("Empty domain editor state");
        settings.Domains.Add(new BlockEntry { Domain = "example.com", ChildMessage = "저장된 메시지" });
        host.RefreshMessageDomains();
        host._messageEditor.CreateControl();
        host._messagesPage.PerformLayout();
        if (host._messageEditor.ReadOnly || !host._messageEditor.Enabled || host._messageEditor.Height < 200)
            throw new Exception($"Editor not usable: {host._messageEditor.Bounds}");
        host._messageEditor.Text = "작성 중인 메시지\r\n두 번째 줄";
        if (!host._messageEditor.Text.Contains("두 번째 줄")) throw new Exception("Multiline input");
        tabs.TabPages.Remove(host._messagesPage); tabs.TabPages.Add(host._messagesPage);
        host.RefreshMessageDomains();
        if (host._messageEditor.ReadOnly) throw new Exception("Admin reentry editor state");
        Console.WriteLine("Message editor: empty state, domain added, multiline input, editor height, admin reentry passed.");
    }
}
