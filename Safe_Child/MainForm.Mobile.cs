using System.Diagnostics;
using QRCoder;

namespace SafeChild;

public sealed partial class MainForm
{
    private MobileControlServer? _mobileServer;
    private bool _mobileBusy;
    private readonly ComboBox _lanAddresses = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 440 };
    private readonly PictureBox _mobileQr = new() { Width = 300, Height = 300, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.White };
    private readonly TextBox _mobileUrl = new() { ReadOnly = true, Width = 700 };
    private readonly Label _mobileStatus = new() { AutoSize = true, MaximumSize = new Size(850, 0) };
    private readonly Label _allowAllStatus = new() { AutoSize = true, Font = new Font("맑은 고딕", 12, FontStyle.Bold), ForeColor = Color.FromArgb(29, 78, 216) };
    private readonly Button _mobileStart = new() { Text = "QR 연결 시작", AutoSize = true };
    private readonly Button _mobileStop = new() { Text = "스마트폰 연결 중지", AutoSize = true };
    private readonly Button _mobileRefresh = new() { Text = "주소 새로고침", AutoSize = true };
    private string? _lastProtectionError;
    private string? _appliedPortSignature;
    private bool? _appliedAllowAll;

    private TabPage BuildMobileTab()
    {
        var page = new TabPage("스마트폰 제어");
        var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoScroll = true, FlowDirection = FlowDirection.TopDown, WrapContents = false, Padding = new Padding(24), BackColor = Color.FromArgb(248, 250, 252) };
        panel.Controls.Add(new Label { Text = "QR로 연결하고 PC의 사이트 허용 시간을 설정하세요", AutoSize = true, Font = new Font(Font, FontStyle.Bold) });
        panel.Controls.Add(new Label { Text = "1. 일반 모드에서 PC의 Wi-Fi/유선 주소를 선택하고 ‘QR 연결 시작’을 누르세요.\n2. 보호자의 스마트폰을 같은 공유기에 연결하고 QR을 스캔하세요.\n3. 스마트폰에서만 관리자 또는 마스터 비밀번호를 입력하고 허용 시간(최대 24시간)을 설정하세요.", AutoSize = true, Margin = new Padding(0, 12, 0, 12) });
        var network = new FlowLayoutPanel { AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, WrapContents = true };
        var refresh = _mobileRefresh;
        _lanAddresses.SelectedIndexChanged += (_, _) => UpdateMobileControls();
        refresh.Click += (_, _) => RefreshLanAddresses();
        network.Controls.AddRange([_lanAddresses, refresh, _mobileStart, _mobileStop]);
        _mobileStart.Click += async (_, _) => await StartMobileAsync();
        _mobileStop.Click += async (_, _) => await StopMobileAsync();
        panel.Controls.Add(network);
        panel.Controls.Add(_mobileQr);
        panel.Controls.Add(_mobileUrl);
        panel.Controls.Add(_mobileStatus);
        panel.Controls.Add(_allowAllStatus);
        var restore = new Button { Text = "허용 즉시 종료 · 보호 복원", AutoSize = true, Tag = "admin", Margin = new Padding(0, 12, 0, 8) };
        restore.Click += (_, _) =>
        {
            if (!_adminUnlocked) return;
            var status = ChangeMobileAllowance(0);
            if (status.Error is not null) MessageBox.Show(this, status.Error, "보호 복원 실패");
        };
        panel.Controls.Add(restore);
        var httpsHelp = MobileHelpCard("HTTPS 연결 안내", "첫 접속 시 로컬 인증서 안내가 나타날 수 있습니다.\n스마트폰에 표시된 주소가 위의 PC 접속 주소와 같은지 확인하세요.",
            Color.FromArgb(239, 246, 255), Color.FromArgb(29, 78, 216));
        var networkHelp = MobileHelpCard("같은 공유기에 연결해 주세요", "PC 네트워크 프로필은 ‘개인’으로 설정하세요.\n게스트 Wi-Fi 또는 기기 간 통신 차단이 켜져 있으면 연결되지 않습니다.",
            Color.FromArgb(240, 253, 250), Color.FromArgb(15, 118, 110));
        var scopeHelp = MobileHelpCard("허용 시간 동안 PC 앱을 켜 두세요", "이 기능은 PC의 Safe Child 차단을 일시 해제합니다.\n정상 종료 시 일시 허용을 끝내고 보호 규칙을 복원합니다.\n강제 종료 후에는 앱을 다시 실행해야 복원되며, 이전 일시 허용은 종료됩니다.",
            Color.FromArgb(255, 251, 235), Color.FromArgb(146, 64, 14));
        panel.Controls.AddRange([httpsHelp, networkHelp, scopeHelp]);
        panel.AutoScrollMargin = new Size(0, 24);
        void ResizeContent()
        {
            var width = Math.Max(240, panel.ClientSize.Width - panel.Padding.Horizontal - SystemInformation.VerticalScrollBarWidth - 8);
            panel.SuspendLayout();
            foreach (Control child in panel.Controls)
            {
                if (child is Label label) label.MaximumSize = new Size(width, 0);
                else if (child is TableLayoutPanel card)
                {
                    card.MaximumSize = Size.Empty;
                    card.MinimumSize = new Size(width, 0);
                    card.MaximumSize = new Size(width, 0);
                    card.Width = width;
                    var height = card.Padding.Vertical;
                    foreach (Control content in card.Controls)
                    {
                        if (content is not Label text) continue;
                        var textWidth = Math.Max(1, width - card.Padding.Horizontal - text.Margin.Horizontal);
                        var textHeight = TextRenderer.MeasureText(text.Text, text.Font, new Size(textWidth, int.MaxValue),
                            TextFormatFlags.WordBreak | TextFormatFlags.TextBoxControl | TextFormatFlags.NoPrefix).Height + 6;
                        text.Size = new Size(textWidth, textHeight);
                        var rowHeight = textHeight + text.Margin.Vertical;
                        card.RowStyles[card.GetRow(text)] = new RowStyle(SizeType.Absolute, rowHeight);
                        height += rowHeight;
                    }
                    card.Height = height;
                }
            }
            network.MaximumSize = new Size(width, 0);
            _mobileUrl.Width = width;
            panel.ResumeLayout();
        }
        panel.ClientSizeChanged += (_, _) => ResizeContent();
        page.Controls.Add(panel);
        ResizeContent();
        RefreshLanAddresses();
        UpdateAllowanceLabel();
        return page;
    }

    private Control MobileHelpCard(string title, string body, Color background, Color accent)
    {
        var card = new TableLayoutPanel
        {
            AutoSize = false, ColumnCount = 1, RowCount = 2,
            BackColor = background, Padding = new Padding(18, 14, 18, 16), Margin = new Padding(0, 8, 0, 4)
        };
        card.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        card.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        card.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        card.Controls.Add(new Label { Text = title, AutoSize = false, UseMnemonic = false, ForeColor = accent, Font = new Font(Font, FontStyle.Bold), Margin = new Padding(0, 0, 0, 7) }, 0, 0);
        card.Controls.Add(new Label { Text = body, AutoSize = false, UseMnemonic = false, ForeColor = Color.FromArgb(51, 65, 85), Margin = Padding.Empty }, 0, 1);
        return card;
    }

    private void RefreshLanAddresses()
    {
        if (_mobileServer is not null) return;
        _lanAddresses.DataSource = LanAddress.Find();
        _mobileStatus.Text = _lanAddresses.Items.Count == 0 ? "연결 가능한 개인 네트워크 주소가 없습니다. Wi-Fi 또는 유선 연결을 확인하세요." : "QR 연결을 시작하면 스마트폰 접속 주소가 표시됩니다.";
        UpdateMobileControls();
    }

    private void UpdateMobileControls()
    {
        var canConfigure = !_mobileBusy && _mobileServer is null;
        _lanAddresses.Enabled = _mobileRefresh.Enabled = canConfigure;
        _mobileStart.Enabled = canConfigure && _lanAddresses.SelectedItem is LanAddress;
        _mobileStop.Enabled = !_mobileBusy && _mobileServer is not null;
    }

    private async Task StartMobileAsync()
    {
        if (_resettingSettings || _mobileBusy || _mobileServer is not null || _lanAddresses.SelectedItem is not LanAddress lan) return;
        _mobileBusy = true;
        UpdateMobileControls();
        var server = new MobileControlServer(
            password => OnUiAsync(() => _store.VerifyPassword(password)),
            minutes => OnUiAsync(() => ChangeMobileAllowance(minutes)));
        _mobileServer = server;
        try
        {
            await server.StartAsync(lan);
            await MobileFirewall.ConfigureAsync(lan.Address.ToString());
            using var generator = new QRCodeGenerator();
            using var data = generator.CreateQrCode(server.Url!, QRCodeGenerator.ECCLevel.M);
            using var png = new PngByteQRCode(data);
            using var stream = new MemoryStream(png.GetGraphic(8));
            using var image = Image.FromStream(stream);
            _mobileQr.Image?.Dispose(); _mobileQr.Image = new Bitmap(image);
            _mobileUrl.Text = server.Url;
            _mobileStatus.Text = $"연결 대기 중 · HTTPS · {lan.Address}:{MobileControlServer.Port}\n인증서 SHA-256: {server.CertificateFingerprint}";
        }
        catch (Exception ex)
        {
            await server.DisposeAsync(); _mobileServer = null;
            try { await MobileFirewall.RemoveAsync(); } catch { }
            _mobileStatus.Text = $"연결 시작 실패: {ex.Message}";
        }
        finally { _mobileBusy = false; UpdateMobileControls(); }
    }

    private async Task StopMobileAsync()
    {
        if (_mobileBusy || _mobileServer is null) return;
        _mobileBusy = true;
        var server = _mobileServer;
        UpdateMobileControls();
        try
        {
            await server.DisposeAsync();
            await MobileFirewall.RemoveAsync();
            _mobileStatus.Text = "스마트폰 연결을 중지했습니다. 이미 설정한 허용 시간은 계속 경과합니다.";
        }
        catch (Exception ex) { _mobileStatus.Text = $"연결 종료 처리: {ex.Message}"; }
        finally
        {
            _mobileServer = null;
            _mobileBusy = false;
            _mobileQr.Image?.Dispose(); _mobileQr.Image = null; _mobileUrl.Clear();
            UpdateMobileControls();
        }
    }

    private Task<T> OnUiAsync<T>(Func<T> action)
    {
        var result = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
        if (_shutdownInProgress || IsDisposed || Disposing) return Task.FromException<T>(new ObjectDisposedException(nameof(MainForm)));
        try
        {
            BeginInvoke((Action)(() =>
            {
                try
                {
                    if (_shutdownInProgress || IsDisposed || Disposing) throw new ObjectDisposedException(nameof(MainForm));
                    result.SetResult(action());
                }
                catch (Exception ex) { result.SetException(ex); }
            }));
        }
        catch (Exception ex) { result.TrySetException(ex); }
        return result.Task;
    }

    private MobileStatus ChangeMobileAllowance(int? minutes)
    {
        if (minutes is { } value)
        {
            if (value is < 0 or > 1440) throw new ArgumentOutOfRangeException(nameof(minutes));
            var previous = _store.Settings.AllowAllUntil;
            var previousCountdown = _store.Settings.AllowAllCountdown;
            _store.Settings.AllowAllUntil = value == 0 ? null : DateTimeOffset.UtcNow.AddMinutes(value);
            _store.Settings.AllowAllCountdown = value == 0 ? null : ElapsedCountdown.Start(value * 60000L);
            try { _store.Save(); }
            catch { _store.Settings.AllowAllUntil = previous; _store.Settings.AllowAllCountdown = previousCountdown; throw; }
            ApplyScheduledDomains(true);
            _domainGrid.Refresh();
        }
        UpdateAllowanceLabel();
        var now = DateTimeOffset.UtcNow;
        var active = _store.Settings.IsAllowAllActive(now);
        return new MobileStatus(active, active ? now.AddMilliseconds(_store.Settings.AllowAllRemaining) : null,
            (int)Math.Ceiling(_store.Settings.AllowAllRemaining / 1000d), _lastProtectionError);
    }

    private void UpdateAllowanceLabel()
    {
        var now = DateTimeOffset.UtcNow;
        _allowAllStatus.Text = _store.Settings.IsAllowAllActive(now)
            ? $"모든 사이트 허용 중 · 남은 시간 {ElapsedCountdown.Format(_store.Settings.AllowAllRemaining)} · 경과 시간 기준"
            : "기존 보호 규칙 적용 중";
    }
}

internal static class MobileFirewall
{
    private const string Rule = "SafeChild Mobile HTTPS";
    public static async Task ConfigureAsync(string localAddress)
    {
        await RemoveAsync();
        await RunAsync(["advfirewall", "firewall", "add", "rule", $"name={Rule}", "dir=in", "action=allow", "protocol=TCP",
            $"localport={MobileControlServer.Port}", $"localip={localAddress}", "remoteip=LocalSubnet", "profile=private,domain",
            $"program={Environment.ProcessPath}", "enable=yes"]);
    }
    public static Task RemoveAsync() => RunAsync(["advfirewall", "firewall", "delete", "rule", $"name={Rule}"], true);
    private static async Task RunAsync(string[] arguments, bool allowMissing = false)
    {
        var info = new ProcessStartInfo("netsh.exe") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in arguments) info.ArgumentList.Add(argument);
        using var process = Process.Start(info) ?? throw new InvalidOperationException("방화벽 설정을 시작하지 못했습니다.");
        var output = process.StandardOutput.ReadToEndAsync(); var error = process.StandardError.ReadToEndAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        try { await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false); }
        catch { try { process.Kill(); } catch { } throw; }
        var detail = (await output.ConfigureAwait(false)) + (await error.ConfigureAwait(false));
        if (process.ExitCode != 0 && !allowMissing) throw new InvalidOperationException("방화벽 설정 실패. 관리자 권한을 확인하세요. " + detail.Trim());
    }
}
