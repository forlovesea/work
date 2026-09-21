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
    private readonly CheckBox _externalMobile = new() { Text = "외부 접속 사용 (관리자 전용)", AutoSize = true };
    private readonly TextBox _externalOrigin = new() { Width = 540, PlaceholderText = "https://myhome.example.com:47831" };
    private readonly TextBox _certificatePath = new() { Width = 440, PlaceholderText = "서버 인증서 .pfx 또는 .p12" };
    private readonly TextBox _certificatePassword = new() { Width = 280, UseSystemPasswordChar = true, PlaceholderText = "인증서 비밀번호 (저장하지 않음)" };
    private readonly Button _browseCertificate = new() { Text = "인증서 선택", AutoSize = true };
    private readonly Button _rotateMobileLink = new() { Text = "외부 접속 링크 새로 발급", AutoSize = true };
    private readonly Button _copyMobileLink = new() { Text = "접속 주소 복사", AutoSize = true };
    private readonly FlowLayoutPanel _externalSettings = new() { AutoSize = true, FlowDirection = FlowDirection.TopDown, WrapContents = false };
    private string? _lastProtectionError;
    private string? _appliedPortSignature;
    private bool? _appliedAllowAll;

    private TabPage BuildMobileTab()
    {
        var page = new TabPage("스마트폰 제어");
        var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoScroll = true, FlowDirection = FlowDirection.TopDown, WrapContents = false, Padding = new Padding(24), BackColor = Color.FromArgb(248, 250, 252) };
        panel.Controls.Add(new Label { Text = "QR로 연결하고 사이트별 보호 설정을 관리하세요", AutoSize = true, Font = new Font(Font, FontStyle.Bold) });
        panel.Controls.Add(new Label { Text = "PC 주소를 선택하고 ‘QR 연결 시작’을 누른 뒤 휴대폰으로 QR을 스캔하세요.\n내부 접속은 같은 공유기에서, 외부 접속은 아래 설정 후 LTE·5G에서도 사용할 수 있습니다.\n휴대폰에서 인증하면 사이트별 차단·요일별 시간표·전체 일시 허용을 관리할 수 있습니다.", AutoSize = true, Margin = new Padding(0, 12, 0, 12) });
        panel.Controls.Add(_externalMobile);
        _externalSettings.Controls.Add(new Label { Text = "외부 HTTPS 주소 (공유기의 외부 포트 포함)", AutoSize = true });
        _externalSettings.Controls.Add(_externalOrigin);
        _externalSettings.Controls.Add(new Label { Text = "이 주소용 서버 인증서 (개인 키 포함 PFX)", AutoSize = true, Margin = new Padding(0, 10, 0, 0) });
        _externalSettings.Controls.Add(_certificatePath);
        _externalSettings.Controls.Add(_browseCertificate);
        _externalSettings.Controls.Add(_certificatePassword);
        _externalSettings.Controls.Add(_rotateMobileLink);
        _externalSettings.Controls.Add(new Label { Text = "인증서 비밀번호는 시작할 때 입력합니다. 재실행 후에는 연결을 다시 시작하세요.\n인증서를 갱신했을 때도 연결 중지 → 새 파일 선택 → 시작으로 반영합니다.\n외부 접속에서는 이 PC에 설정한 관리자 비밀번호로만 로그인합니다.", AutoSize = true });
        panel.Controls.Add(_externalSettings);
        LoadMobilePreferences();
        _externalMobile.CheckedChanged += (_, _) => UpdateMobileControls();
        _browseCertificate.Click += (_, _) =>
        {
            if (!_adminUnlocked || _mobileBusy || _mobileServer is not null) return;
            using var picker = new OpenFileDialog { Title = "외부 HTTPS 서버 인증서 선택", Filter = "인증서 파일 (*.pfx;*.p12)|*.pfx;*.p12", CheckFileExists = true };
            if (picker.ShowDialog(this) == DialogResult.OK) _certificatePath.Text = picker.FileName;
        };
        _rotateMobileLink.Click += (_, _) => RotateMobileLink();
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
        panel.Controls.Add(_copyMobileLink);
        _copyMobileLink.Click += (_, _) =>
        {
            if (_mobileServer?.Url is not { } url) return;
            try { Clipboard.SetText(url); }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "주소 복사 실패"); }
        };
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
        var httpsHelp = MobileHelpCard("HTTPS 인증서", "내부 접속은 PC가 생성한 로컬 인증서를 사용합니다.\n외부 접속은 등록한 주소와 일치하고 유효 기간 내인 PFX 인증서가 필요합니다.\n휴대폰이 신뢰하는 인증기관의 인증서를 사용하면 인증서 경고 없이 접속할 수 있습니다.",
            Color.FromArgb(239, 246, 255), Color.FromArgb(29, 78, 216));
        var networkHelp = MobileHelpCard("외부 접속 설정 순서", "PC 네트워크 프로필을 ‘개인’으로 설정하고 내부 IP를 고정하세요.\nDDNS 주소가 집 공인 IP를 가리키게 설정하세요.\n공유기의 TCP 외부 포트를 선택한 PC 주소의 47831 포트로 전달하세요.\n접속 주소 전체를 저장한 뒤 휴대폰 Wi-Fi를 끄고 LTE·5G로 확인하세요.\n공유기가 공인 IP를 받지 못하거나 이중 공유기이면 상위 장비 설정도 필요합니다.",
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
            _externalSettings.MaximumSize = new Size(width, 0);
            var fieldWidth = Math.Max(1, width - _externalSettings.Margin.Horizontal - 6);
            _externalOrigin.Width = _certificatePath.Width = fieldWidth;
            foreach (var label in _externalSettings.Controls.OfType<Label>()) label.MaximumSize = new Size(fieldWidth, 0);
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
        var canConfigure = !_mobileBusy && _mobileServer is null && !_resettingSettings && !_shutdownInProgress;
        _lanAddresses.Enabled = _mobileRefresh.Enabled = canConfigure;
        _externalMobile.Enabled = canConfigure && _adminUnlocked;
        _externalSettings.Visible = _externalMobile.Checked;
        _externalSettings.Enabled = canConfigure && _adminUnlocked;
        _mobileStart.Enabled = canConfigure && _lanAddresses.SelectedItem is LanAddress && (!_externalMobile.Checked || _adminUnlocked);
        _mobileStop.Enabled = !_mobileBusy && _mobileServer is not null && (!_mobileServer.External || _adminUnlocked);
        _copyMobileLink.Enabled = _mobileServer?.Url is not null;
    }

    private void LoadMobilePreferences()
    {
        var settings = _store.Settings.MobileConnection;
        _externalMobile.Checked = settings.ExternalEnabled;
        _externalOrigin.Text = settings.PublicOrigin;
        _certificatePath.Text = settings.CertificatePath;
        _certificatePassword.Clear();
    }

    private void RotateMobileLink()
    {
        if (!_adminUnlocked || _mobileBusy || _mobileServer is not null || _resettingSettings || _shutdownInProgress) return;
        var settings = _store.Settings.MobileConnection;
        var previous = settings.AccessToken;
        settings.AccessToken = MobileConnectionOptions.NewAccessToken();
        try { _store.Save(); _mobileStatus.Text = "새 외부 링크를 발급했습니다. 연결을 시작한 뒤 새 주소를 휴대폰에 저장하세요. 이전 링크는 사용할 수 없습니다."; }
        catch (Exception ex) { settings.AccessToken = previous; MessageBox.Show(this, ex.Message, "링크 발급 실패"); }
    }

    private async Task StartMobileAsync()
    {
        if (_resettingSettings || _mobileBusy || _mobileServer is not null || _lanAddresses.SelectedItem is not LanAddress lan) return;
        var external = _externalMobile.Checked;
        if (external && !_adminUnlocked) return;
        _mobileBusy = true;
        UpdateMobileControls();
        var server = new MobileControlServer(
            password => OnUiAsync(() => external ? _store.VerifyAdministratorPassword(password) : _store.VerifyPassword(password)),
            minutes => OnUiAsync(() => ChangeMobileAllowance(minutes)),
            command => OnUiAsync(() => ChangeMobileRules(command)));
        _mobileServer = server;
        try
        {
            var previous = _store.Settings.MobileConnection;
            var settings = new MobileConnectionSettings
            {
                ExternalEnabled = external,
                PublicOrigin = external ? MobileConnectionOptions.ParseOrigin(_externalOrigin.Text).GetLeftPart(UriPartial.Authority) : previous.PublicOrigin,
                CertificatePath = external ? _certificatePath.Text.Trim() : previous.CertificatePath,
                AccessToken = previous.AccessToken is { Length: 48 } && previous.AccessToken.All(Uri.IsHexDigit)
                    ? previous.AccessToken : MobileConnectionOptions.NewAccessToken()
            };
            var options = external ? new MobileConnectionOptions(settings.PublicOrigin, settings.CertificatePath,
                _certificatePassword.Text, settings.AccessToken) : null;
            await server.StartAsync(lan, external: options);
            await MobileFirewall.ConfigureAsync(lan.Address.ToString(), external);
            if (external || _adminUnlocked)
            {
                _store.Settings.MobileConnection = settings;
                try { _store.Save(); }
                catch { _store.Settings.MobileConnection = previous; throw; }
            }
            using var generator = new QRCodeGenerator();
            using var data = generator.CreateQrCode(server.Url!, QRCodeGenerator.ECCLevel.M);
            using var png = new PngByteQRCode(data);
            using var stream = new MemoryStream(png.GetGraphic(8));
            using var image = Image.FromStream(stream);
            _mobileQr.Image?.Dispose(); _mobileQr.Image = new Bitmap(image);
            _mobileUrl.Text = server.Url;
            _mobileStatus.Text = external
                ? $"외부 접속 대기 중 · 공유기 TCP {new Uri(settings.PublicOrigin).Port} → {lan.Address}:{MobileControlServer.Port}\n인증서 만료: {server.CertificateExpiresAt:yyyy-MM-dd HH:mm}\nLTE·5G에서 위 주소로 접속해 확인하세요. 인증서 SHA-256: {server.CertificateFingerprint}"
                : $"내부 접속 대기 중 · HTTPS · {lan.Address}:{MobileControlServer.Port}\n인증서 SHA-256: {server.CertificateFingerprint}";
        }
        catch (Exception ex)
        {
            try { await server.DisposeAsync(); } catch { }
            _mobileServer = null;
            _mobileQr.Image?.Dispose(); _mobileQr.Image = null; _mobileUrl.Clear();
            try { await MobileFirewall.RemoveAsync(); } catch { }
            _mobileStatus.Text = $"연결 시작 실패: {ex.Message}";
        }
        finally { _certificatePassword.Clear(); _mobileBusy = false; UpdateMobileControls(); }
    }

    private async Task StopMobileAsync()
    {
        if (_mobileBusy || _mobileServer is null) return;
        if (_mobileServer.External && !_adminUnlocked) return;
        _mobileBusy = true;
        var server = _mobileServer;
        UpdateMobileControls();
        try
        {
            try { await server.DisposeAsync(); }
            finally { await MobileFirewall.RemoveAsync(); }
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

    private MobileRulesResult ChangeMobileRules(MobileRuleCommand? command)
    {
        if (_resettingSettings) throw new MobileRuleException(409, "PC 설정 초기화 중입니다. 잠시 후 다시 시도하세요.");
        if (command is not null)
        {
            MobileRules.Execute(_store.Settings, command, BlockingService.NormalizeDomain, _store.Save);
            ApplyScheduledDomains(true);
            RefreshRules();
        }
        return MobileRules.Read(_store.Settings, _lastProtectionError);
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

