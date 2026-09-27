using System.Net;
using System.Reflection;
using System.Runtime.CompilerServices;

namespace SafeChild;

internal static class Program
{
    [STAThread]
    private static void Main() => MainForm.CheckMobileSettings();
}

// Only builds the production settings page. No server, protection change, or real settings file is used.
public sealed partial class MainForm : Form
{
    private readonly SettingsStore _store = (SettingsStore)RuntimeHelpers.GetUninitializedObject(typeof(SettingsStore));
    private bool _adminUnlocked;
    private bool _resettingSettings;
    private bool _shutdownInProgress = false;
    private readonly DataGridView _domainGrid = new();
    private void ApplyScheduledDomains(bool force) => throw new InvalidOperationException("Protection must not run in UI checks");
    private void RefreshRules() => throw new InvalidOperationException("Rules must not change in UI checks");

    public static void CheckMobileSettings()
    {
        using var host = new MainForm { ClientSize = new Size(960, 720), Font = new Font("맑은 고딕", 9F) };
        var settings = new AppSettings { MobileConnection = new() { ExternalEnabled = true,
            PublicOrigin = "https://parent.example.test:44443", CertificatePath = @"C:\certificates\server.pfx" } };
        typeof(SettingsStore).GetField("<Settings>k__BackingField", BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(host._store, settings);
        var tabs = new TabControl { Dock = DockStyle.Fill };
        host.Controls.Add(tabs);
        var page = host.BuildMobileTab(); tabs.TabPages.Add(page);
        host.CreateControl(); tabs.CreateControl(); page.CreateControl(); host.PerformLayout(); page.PerformLayout();
        host._lanAddresses.DataSource = new[] { new LanAddress("test", IPAddress.Parse("192.168.35.100"), IPAddress.Parse("255.255.255.0")) };
        host.UpdateMobileControls();
        void Check(bool condition, string name) { if (!condition) throw new Exception(name); Console.WriteLine("PASS: " + name); }
        Check(host._externalMobile.Checked && host._externalOrigin.Text == settings.MobileConnection.PublicOrigin &&
            host._certificatePath.Text == settings.MobileConnection.CertificatePath, "Stored external preferences restored");
        Check(!host._externalMobile.Enabled && !host._externalSettings.Enabled && !host._mobileStart.Enabled, "Locked PC cannot configure or start external service");
        host._adminUnlocked = true; host.UpdateMobileControls();
        Check(host._externalSettings.Enabled && host._mobileStart.Enabled, "Administrator can configure and start external service");
        Check(host._certificatePassword.UseSystemPasswordChar && host._certificatePassword.Text == "", "Certificate password starts empty and masked");
        host._mobileBusy = true; host.UpdateMobileControls();
        Check(!host._externalSettings.Enabled && !host._externalMobile.Enabled && !host._mobileStart.Enabled, "Settings frozen during start or stop");
        host._mobileBusy = false; host._resettingSettings = true; host.UpdateMobileControls();
        Check(!host._externalSettings.Enabled && !host._mobileStart.Enabled, "Settings disabled during reset");
        host._resettingSettings = false; host._externalMobile.Checked = false; host._adminUnlocked = false; host.UpdateMobileControls();
        Check(host._mobileStart.Enabled, "Local QR start remains available when locked");
        Check(!host._copyMobileLink.Enabled, "No stale link can be copied while disconnected");
        settings.MobileConnection = new(); host._certificatePassword.Text = "temporary"; host.LoadMobilePreferences(); host.UpdateMobileControls();
        Check(!host._externalMobile.Checked && host._externalOrigin.Text == "" && host._certificatePassword.Text == "", "Reset clears external preferences and password field");
        host.ClientSize = new Size(640, 600); host.PerformLayout(); page.PerformLayout();
        Check(host._externalOrigin.Width > 200 && host._externalOrigin.Width < host.ClientSize.Width, "External fields fit a narrow PC window");
        Console.WriteLine("10 mobile settings UI checks passed.");
    }
}

internal static class BlockingService
{
    public static string NormalizeDomain(string value) => new Uri("https://" + value).IdnHost;
}
