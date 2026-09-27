using Microsoft.Win32;

namespace SafeChild;

public sealed partial class MainForm : Form
{
    private readonly SettingsStore _store = new();
    private readonly BrowserHistoryService _history = new();
    private readonly NotifyIcon _tray = new();
    private readonly TabControl _tabs = new StyledTabControl { Dock = DockStyle.Fill };
    private readonly Label _lockState = new() { AutoSize = true, Font = new Font("맑은 고딕", 10, FontStyle.Bold) };
    private readonly Button _loginButton = new() { Text = "관리자 모드", AutoSize = true };
    private readonly Button _resetPasswordButton = new() { Text = "비밀번호 초기화", AutoSize = true };
    private readonly Button _resetSettingsButton = new() { Text = "설정초기화", AutoSize = true, Visible = false };
    private bool _resettingSettings;
    private readonly Button _exitButton = new() { Text = "프로그램 종료", AutoSize = true };
    private readonly Button _autoStartButton = new() { Text = "재부팅후 자동실행", AutoSize = true, Visible = false };
    private readonly Button _removeAutoStartButton = new() { Text = "자동실행 삭제", AutoSize = true, Visible = false };
    private readonly TableLayoutPanel _autoStartFooter = new()
    {
        Dock = DockStyle.Bottom, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
        ColumnCount = 1, RowCount = 1, Padding = new Padding(16, 12, 16, 12),
        BackColor = Color.FromArgb(248, 250, 252), Visible = false
    };
    private bool _autoStartBusy;
    private readonly DataGridView _domainGrid = Grid();
    private readonly DataGridView _portGrid = Grid();
    private readonly DataGridView _historyGrid = Grid();
    private readonly TextBox _domainInput = new() { PlaceholderText = "예: youtube.com 또는 https://youtube.com/watch", Width = 420 };
    private readonly NumericUpDown _portInput = new() { Minimum = 1, Maximum = 65535, Width = 100, Tag = "admin" };
    private readonly NumericUpDown _portEndInput = new() { Minimum = 1, Maximum = 65535, Width = 100, Enabled = false };
    private readonly CheckBox _portRangeEnabled = new() { Text = "범위", AutoSize = true, Tag = "admin", Margin = new Padding(4, 12, 4, 0) };
    private readonly ComboBox _protocol = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 90 };
    private readonly DateTimePicker _from = new() { Format = DateTimePickerFormat.Short, Width = 120 };
    private readonly DateTimePicker _to = new() { Format = DateTimePickerFormat.Short, Width = 120 };
    private readonly TextBox _search = new() { PlaceholderText = "제목 또는 URL 검색", Width = 240 };
    private readonly Label _historyStatus = new() { AutoSize = true, ForeColor = Color.DimGray };
    private readonly System.Windows.Forms.Timer _collectionTimer = new() { Interval = 60_000 };
    private readonly Button _collectionButton = new() { Text = "중지", AutoSize = true };
    private readonly Button _collectNowButton = new() { Text = "지금 방문 기록 수집", AutoSize = true };
    private readonly Button _collectAndQueryButton = new() { Text = "수집 후 조회", AutoSize = true };
    private bool _collectionEnabled = true;
    private CancellationTokenSource? _collectionCancellation;
    private bool _adminUnlocked;
    private bool _allowExit;
    private bool _shutdownInProgress;
    private bool _shutdownComplete;
    private readonly System.Windows.Forms.Timer _domainTimer = new() { Interval = 1000 };
    private readonly Label _domainStatus = new() { AutoSize = true, ForeColor = Color.DimGray, Padding = new Padding(8) };
    private string? _appliedDomainSignature;
    private long _lastTimerCheckpoint = Environment.TickCount64;

    public MainForm()
    {
        Text = "Safe Child - Windows 자녀 보호";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(1000, 650);
        Size = new Size(1220, 780);
        Font = new Font("맑은 고딕", 9F);
        Icon = SystemIcons.Shield;
        BuildUi();
        ConfigureTray();
        _collectionTimer.Tick += async (_, _) => await CollectHistoryAsync(false);
        _domainTimer.Tick += (_, _) =>
        {
            SaveTimerCheckpoint();
            ApplyScheduledDomains();
            RefreshHostsStatus();
            UpdateAllowanceLabel();
            UpdateMessageConnection();
            _domainGrid.InvalidateColumn(_domainGrid.Columns[nameof(BlockEntry.RemainingTime)]!.Index);
            _domainGrid.InvalidateColumn(_domainGrid.Columns[nameof(BlockEntry.CurrentState)]!.Index);
            _portGrid.InvalidateColumn(_portGrid.Columns[nameof(PortEntry.RemainingTime)]!.Index);
            _portGrid.InvalidateColumn(_portGrid.Columns[nameof(PortEntry.CurrentState)]!.Index);
        };
        SystemEvents.SessionEnding += OnSessionEnding;
        Shown += OnFirstShown;
        FormClosing += OnFormClosing;
        Resize += (_, _) => { if (WindowState == FormWindowState.Minimized) HideToTray(); };
    }

    private void BuildUi()
    {
        var header = new Panel { Dock = DockStyle.Top, Height = 58, Padding = new Padding(14, 10, 14, 8), BackColor = Color.FromArgb(239, 246, 255) };
        var title = new Label { Text = "Safe Child", AutoSize = true, Font = new Font("맑은 고딕", 16, FontStyle.Bold), ForeColor = Color.FromArgb(30, 64, 175) };
        var headerFlow = new FlowLayoutPanel { Dock = DockStyle.Right, AutoSize = true, WrapContents = false };
        _loginButton.Click += (_, _) => ToggleAdmin();
        _resetPasswordButton.Click += (_, _) => ResetPassword();
        _resetSettingsButton.Click += async (_, _) => await ResetSettingsAsync();
        _exitButton.Click += (_, _) => AdminExit();
        headerFlow.Controls.AddRange([_lockState, _loginButton, _resetPasswordButton, _resetSettingsButton, _exitButton]);
        header.Controls.Add(title); header.Controls.Add(headerFlow);
        Controls.Add(_tabs); Controls.Add(BuildAutoStartFooter()); Controls.Add(header);

        _tabs.TabPages.Add(BuildDashboardTab());
        _tabs.TabPages.Add(BuildDomainTab());
        _tabs.TabPages.Add(BuildPortTab());
        _tabs.TabPages.Add(BuildHistoryTab());
        _tabs.TabPages.Add(BuildMobileTab());
        _messagesPage = BuildMessagesTab();
        SetAdminState(false);
    }

    private TabPage BuildDashboardTab()
    {
        var page = new TabPage("상태");
        var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown, Padding = new Padding(24), WrapContents = false, AutoScroll = true };
        panel.Controls.Add(new Label { Text = "보호 상태", AutoSize = true, Font = new Font(Font, FontStyle.Bold) });
        panel.Controls.Add(new Label { Text = "• 프로그램은 최소화하거나 닫기(X)를 눌러도 트레이에서 계속 실행됩니다.\n• 종료는 Windows 시스템 종료 또는 관리자 인증 후에만 가능합니다.\n• URL 차단은 HTTPS 보안 구조상 도메인 단위로 적용됩니다.\n• 접속 시간은 Chrome/Edge 방문 간격으로 계산한 최대 30분의 추정치입니다.", AutoSize = true, MaximumSize = new Size(900, 0), Padding = new Padding(0, 10, 0, 10) });
        var collect = _collectNowButton;
        collect.Click += async (_, _) => await CollectHistoryAsync(true);
        panel.Controls.Add(collect);
        page.Controls.Add(panel);
        return page;
    }

    private Control BuildAutoStartFooter()
    {
        var actions = new FlowLayoutPanel
        {
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            Anchor = AnchorStyles.None, WrapContents = false, Margin = Padding.Empty
        };
        StyleDomainAction(_autoStartButton, Color.FromArgb(37, 99, 235), Color.White, Color.FromArgb(37, 99, 235));
        _autoStartButton.Click += async (_, _) => await ConfigureAutoStartAsync(true);
        StyleDomainAction(_removeAutoStartButton, Color.FromArgb(254, 242, 242), Color.FromArgb(185, 28, 28), Color.FromArgb(254, 202, 202));
        _removeAutoStartButton.Click += async (_, _) => await ConfigureAutoStartAsync(false);
        _autoStartButton.MinimumSize = _removeAutoStartButton.MinimumSize = new Size(170, 38);
        _autoStartButton.Margin = new Padding(0, 0, 12, 0);
        _removeAutoStartButton.Margin = Padding.Empty;
        actions.Controls.AddRange([_autoStartButton, _removeAutoStartButton]);
        _autoStartFooter.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        _autoStartFooter.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        _autoStartFooter.Controls.Add(actions, 0, 0);
        return _autoStartFooter;
    }

    private async Task ConfigureAutoStartAsync(bool enable)
    {
        if (!_adminUnlocked || _autoStartBusy || _resettingSettings || _shutdownInProgress) return;
        _autoStartBusy = true;
        _autoStartButton.Enabled = _removeAutoStartButton.Enabled = false;
        var button = enable ? _autoStartButton : _removeAutoStartButton;
        var operation = enable ? "설정" : "삭제";
        button.Text = $"자동실행 {operation} 중…";
        try
        {
            await AutoStartService.ConfigureAsync(enable);
            if (!_shutdownInProgress && enable)
                MessageBox.Show(this, $"이 PC에 자동 실행을 등록했습니다.\n\n재부팅 후 현재 Windows 계정({System.Security.Principal.WindowsIdentity.GetCurrent().Name})에 로그인하면 관리자 권한으로 자동 실행됩니다.\n앱의 관리자 모드는 계속 잠금 상태로 시작합니다.\n\n프로그램 폴더를 옮기면 새 위치에서 이 버튼을 다시 눌러주세요.", "자동실행 설정 완료", MessageBoxButtons.OK, MessageBoxIcon.Information);
            else if (!_shutdownInProgress)
                MessageBox.Show(this, "현재 Windows 계정의 자동실행 등록을 삭제했습니다.\n다음 재부팅 후 로그인해도 프로그램이 자동으로 실행되지 않습니다.", "자동실행 삭제 완료", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception ex)
        {
            if (!_shutdownInProgress) MessageBox.Show(this, ex.Message, $"자동실행 {operation} 실패", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        finally
        {
            _autoStartBusy = false;
            if (!IsDisposed)
            {
                _autoStartButton.Text = "재부팅후 자동실행";
                _removeAutoStartButton.Text = "자동실행 삭제";
                _autoStartButton.Enabled = _removeAutoStartButton.Enabled = _adminUnlocked && !_resettingSettings && !_shutdownInProgress;
            }
        }
    }

    private TabPage BuildDomainTab()
    {
        var page = new TabPage("URL/도메인 차단");
        var top = new TableLayoutPanel
        {
            Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            ColumnCount = 2, RowCount = 2, Padding = new Padding(8)
        };
        top.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        top.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        top.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        top.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        var actions = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            WrapContents = true, Margin = Padding.Empty
        };
        var bulkActions = new FlowLayoutPanel
        {
            Anchor = AnchorStyles.Top | AnchorStyles.Right, AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink, WrapContents = false, Margin = Padding.Empty
        };
        var add = new Button { Text = "등록 및 차단", AutoSize = true, Tag = "admin" };
        var toggle = new Button { Text = "선택 항목 차단/해제", AutoSize = true, Tag = "admin" };
        var remove = new Button { Text = "선택 삭제", AutoSize = true, Tag = "admin" };
        var timeSettings = new Button { Text = "시간 설정", AutoSize = true, Tag = "admin" };
        var refreshHosts = new Button { Text = "hosts 상태 새로고침", AutoSize = true };
        StyleDomainAction(add, Color.FromArgb(37, 99, 235), Color.White, Color.FromArgb(37, 99, 235));
        StyleDomainAction(toggle, Color.FromArgb(240, 253, 250), Color.FromArgb(15, 118, 110), Color.FromArgb(153, 246, 228));
        StyleDomainAction(remove, Color.FromArgb(255, 241, 242), Color.FromArgb(190, 18, 60), Color.FromArgb(254, 205, 211));
        StyleDomainAction(timeSettings, Color.FromArgb(245, 243, 255), Color.FromArgb(109, 40, 217), Color.FromArgb(221, 214, 254));
        StyleDomainAction(refreshHosts, Color.FromArgb(236, 254, 255), Color.FromArgb(14, 116, 144), Color.FromArgb(165, 243, 252));
        refreshHosts.Click += (_, _) => RefreshHostsStatus(true);
        timeSettings.Click += (_, _) => EditDomainSchedule();
        add.Click += (_, _) => AddDomain(); toggle.Click += (_, _) => ToggleDomain(); remove.Click += (_, _) => RemoveDomain();
        var selectAll = new Button { Text = "전체 선택", AutoSize = true, Tag = "admin" };
        var clearAll = new Button { Text = "전체 해제", AutoSize = true, Tag = "admin" };
        StyleDomainAction(selectAll, Color.FromArgb(241, 245, 249), Color.FromArgb(51, 65, 85), Color.FromArgb(203, 213, 225));
        StyleDomainAction(clearAll, Color.FromArgb(241, 245, 249), Color.FromArgb(51, 65, 85), Color.FromArgb(203, 213, 225));
        Button[] domainButtons = [add, toggle, remove, timeSettings, refreshHosts, selectAll, clearAll];
        var actionHeight = domainButtons.Max(button => button.GetPreferredSize(Size.Empty).Height);
        foreach (var button in domainButtons) button.MinimumSize = new Size(0, actionHeight);
        var inputFrame = new Panel
        {
            Width = _domainInput.Width, Height = actionHeight, BackColor = Color.White,
            BorderStyle = BorderStyle.FixedSingle, Margin = new Padding(4, 3, 4, 6)
        };
        _domainInput.BorderStyle = BorderStyle.None;
        inputFrame.Controls.Add(_domainInput);
        void AlignDomainInput()
        {
            _domainInput.SetBounds(10, Math.Max(0, (inputFrame.ClientSize.Height - _domainInput.PreferredHeight) / 2),
                Math.Max(1, inputFrame.ClientSize.Width - 20), _domainInput.PreferredHeight);
        }
        inputFrame.Resize += (_, _) => AlignDomainInput();
        add.SizeChanged += (_, _) => inputFrame.Height = add.Height;
        AlignDomainInput();
        selectAll.Click += (_, _) => SetAllDomainsActive(true);
        clearAll.Click += (_, _) => SetAllDomainsActive(false);
        _domainGrid.CellMouseDoubleClick += (_, e) =>
        {
            if (!_adminUnlocked || e.Button != MouseButtons.Left || e.RowIndex < 0 || e.ColumnIndex < 0) return;
            if (_domainGrid.Columns[e.ColumnIndex].DataPropertyName == nameof(BlockEntry.TimeEnabled))
            {
                _domainGrid.CurrentCell = _domainGrid.Rows[e.RowIndex].Cells[e.ColumnIndex];
                EditDomainSchedule();
                return;
            }
            if (_domainGrid.Columns[e.ColumnIndex].DataPropertyName != nameof(BlockEntry.Active)) return;
            if (_domainGrid.Rows[e.RowIndex].DataBoundItem is not BlockEntry item) return;
            item.Active = !item.Active;
            SaveAndApplyDomains();
        };
        actions.Controls.AddRange([inputFrame, add]);
        var selectionActions = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, WrapContents = true, Margin = Padding.Empty };
        selectionActions.Controls.AddRange([toggle, remove, timeSettings, refreshHosts]);
        bulkActions.Controls.AddRange([selectAll, clearAll]);
        top.Controls.Add(actions, 0, 0);
        top.Controls.Add(bulkActions, 1, 0);
        top.Controls.Add(selectionActions, 0, 1); top.SetColumnSpan(selectionActions, 2);
        _domainGrid.AutoGenerateColumns = false;
        _domainGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(BlockEntry.Domain), HeaderText = "도메인", FillWeight = 35 });
        _domainGrid.Columns.Add(new DataGridViewCheckBoxColumn { DataPropertyName = nameof(BlockEntry.Active), HeaderText = "차단 선택", Width = 85, AutoSizeMode = DataGridViewAutoSizeColumnMode.None });
        _domainGrid.Columns.Add(new DataGridViewCheckBoxColumn { DataPropertyName = nameof(BlockEntry.TimeEnabled), HeaderText = "시간 적용", Width = 85, AutoSizeMode = DataGridViewAutoSizeColumnMode.None });
        _domainGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(BlockEntry.TimeDescription), HeaderText = "시간 설정", FillWeight = 65 });
        _domainGrid.Columns.Add(new DataGridViewTextBoxColumn { Name = nameof(BlockEntry.CurrentState), DataPropertyName = nameof(BlockEntry.CurrentState), HeaderText = "설정 상태", Width = 85, AutoSizeMode = DataGridViewAutoSizeColumnMode.None });
        _domainGrid.Columns.Add(new DataGridViewTextBoxColumn { Name = nameof(BlockEntry.RemainingTime), DataPropertyName = nameof(BlockEntry.RemainingTime), HeaderText = "남은 시간", Width = 190, AutoSizeMode = DataGridViewAutoSizeColumnMode.None, SortMode = DataGridViewColumnSortMode.NotSortable });
        _domainGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(BlockEntry.CreatedAt), HeaderText = "등록 일시", Width = 150, AutoSizeMode = DataGridViewAutoSizeColumnMode.None, DefaultCellStyle = new DataGridViewCellStyle { Format = "yyyy-MM-dd HH:mm" } });
        _domainGrid.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "HostsActualState", HeaderText = "hosts 실제 상태", Width = 240,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None, SortMode = DataGridViewColumnSortMode.NotSortable,
            DefaultCellStyle = new DataGridViewCellStyle
            {
                Font = new Font(Font, FontStyle.Bold), Alignment = DataGridViewContentAlignment.MiddleCenter,
                Padding = new Padding(6, 0, 6, 0)
            }
        });
        _domainGrid.CellFormatting += FormatHostsStatus;
        _domainGrid.CellFormatting += (_, e) =>
        {
            if (!_store.Settings.IsAllowAllActive(DateTimeOffset.UtcNow)) return;
            var property = _domainGrid.Columns[e.ColumnIndex].DataPropertyName;
            if (property == nameof(BlockEntry.CurrentState)) { e.Value = "일시 허용"; e.FormattingApplied = true; }
            if (property == nameof(BlockEntry.RemainingTime))
            {
                e.Value = $"허용 종료까지 {ElapsedCountdown.Format(_store.Settings.AllowAllRemaining)}";
                e.FormattingApplied = true;
            }
        };
        _domainStatus.Text = "시간 적용은 ‘시간 설정’에서 변경합니다. 시간 밖에는 차단이 해제됩니다.";
        var statusBar = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 100, FlowDirection = FlowDirection.TopDown, WrapContents = false, AutoScroll = true };
        statusBar.Controls.Add(_domainStatus);
        statusBar.Controls.Add(_hostsCheckLabel);
        statusBar.Controls.Add(new Label { AutoSize = true, Padding = new Padding(8, 0, 8, 0), Text = "hosts 기준 상태이며 실제 브라우저 접속 여부를 검사하지 않습니다. 해제는 hosts 차단 항목이 없다는 뜻입니다." });
        page.Controls.Add(_domainGrid); page.Controls.Add(top); page.Controls.Add(statusBar);
        return page;
    }

    private void StyleDomainAction(Button button, Color background, Color foreground, Color border)
    {
        button.FlatStyle = FlatStyle.Flat;
        button.UseVisualStyleBackColor = false;
        button.Font = new Font(Font, FontStyle.Bold);
        button.Padding = new Padding(10, 6, 10, 6);
        button.Margin = new Padding(4, 3, 4, 6);
        button.MinimumSize = new Size(0, 36);
        button.FlatAppearance.BorderSize = 1;
        button.FlatAppearance.MouseOverBackColor = ControlPaint.Dark(background, 0.04f);
        button.FlatAppearance.MouseDownBackColor = ControlPaint.Dark(background, 0.10f);
        void UpdateColors()
        {
            button.BackColor = button.Enabled ? background : Color.FromArgb(241, 245, 249);
            button.ForeColor = button.Enabled ? foreground : Color.FromArgb(148, 163, 184);
            button.FlatAppearance.BorderColor = button.Enabled ? border : Color.FromArgb(226, 232, 240);
            button.Cursor = button.Enabled ? Cursors.Hand : Cursors.Default;
        }
        button.EnabledChanged += (_, _) => UpdateColors();
        UpdateColors();
    }

    private TabPage BuildPortTab()
    {
        var page = new TabPage("포트 차단");
        var top = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, ColumnCount = 2, RowCount = 2, Padding = new Padding(8) };
        top.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        top.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        top.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        top.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, WrapContents = true, Margin = Padding.Empty };
        var bulk = new FlowLayoutPanel { Anchor = AnchorStyles.Top | AnchorStyles.Right, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, WrapContents = false, Margin = Padding.Empty };
        _protocol.Items.AddRange(["TCP", "UDP"]); _protocol.SelectedIndex = 0;
        var add = new Button { Text = "등록 및 차단", AutoSize = true, Tag = "admin" };
        var toggle = new Button { Text = "선택 항목 차단/해제", AutoSize = true, Tag = "admin" };
        var remove = new Button { Text = "선택 삭제", AutoSize = true, Tag = "admin" };
        add.Click += (_, _) => AddPort(); toggle.Click += (_, _) => TogglePort(); remove.Click += (_, _) => RemovePort();
        var timeSettings = new Button { Text = "시간 설정", AutoSize = true, Tag = "admin" };
        var selectAll = new Button { Text = "전체 선택", AutoSize = true, Tag = "admin" };
        var clearAll = new Button { Text = "전체 해제", AutoSize = true, Tag = "admin" };
        StyleDomainAction(add, Color.FromArgb(37, 99, 235), Color.White, Color.FromArgb(37, 99, 235));
        StyleDomainAction(toggle, Color.FromArgb(240, 253, 250), Color.FromArgb(15, 118, 110), Color.FromArgb(153, 246, 228));
        StyleDomainAction(remove, Color.FromArgb(255, 241, 242), Color.FromArgb(190, 18, 60), Color.FromArgb(254, 205, 211));
        StyleDomainAction(timeSettings, Color.FromArgb(245, 243, 255), Color.FromArgb(109, 40, 217), Color.FromArgb(221, 214, 254));
        foreach (var button in new[] { selectAll, clearAll })
            StyleDomainAction(button, Color.FromArgb(241, 245, 249), Color.FromArgb(51, 65, 85), Color.FromArgb(203, 213, 225));
        Button[] buttons = [add, toggle, remove, timeSettings, selectAll, clearAll];
        var height = buttons.Max(button => button.GetPreferredSize(Size.Empty).Height);
        foreach (var button in buttons) button.MinimumSize = new Size(0, height);
        Control InputFrame(Control input)
        {
            var frame = new Panel { Width = input.Width + 16, Height = height, BackColor = Color.White, BorderStyle = BorderStyle.FixedSingle, Margin = new Padding(4, 3, 4, 6) };
            frame.Controls.Add(input);
            void Align() { input.Location = new Point(7, Math.Max(0, (frame.ClientSize.Height - input.Height) / 2)); }
            frame.Resize += (_, _) => Align();
            add.SizeChanged += (_, _) => frame.Height = add.Height;
            Align(); return frame;
        }
        timeSettings.Click += (_, _) => EditPortSchedule();
        selectAll.Click += (_, _) => SetAllPortsActive(true);
        clearAll.Click += (_, _) => SetAllPortsActive(false);
        _portRangeEnabled.CheckedChanged += (_, _) =>
        {
            _portEndInput.Enabled = _adminUnlocked && _portRangeEnabled.Checked;
            if (_portRangeEnabled.Checked && _portEndInput.Value < _portInput.Value) _portEndInput.Value = _portInput.Value;
        };
        actions.Controls.AddRange([new Label { Text = "시작 포트", AutoSize = true, Margin = new Padding(3, 12, 3, 0) }, InputFrame(_portInput), _portRangeEnabled,
            new Label { Text = "끝 포트", AutoSize = true, Margin = new Padding(3, 12, 3, 0) }, InputFrame(_portEndInput), InputFrame(_protocol), add]);
        var selectionActions = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, WrapContents = true, Margin = Padding.Empty };
        selectionActions.Controls.AddRange([toggle, remove, timeSettings]);
        bulk.Controls.AddRange([selectAll, clearAll]);
        top.Controls.Add(actions, 0, 0); top.Controls.Add(bulk, 1, 0);
        top.Controls.Add(selectionActions, 0, 1); top.SetColumnSpan(selectionActions, 2);
        _portGrid.AutoGenerateColumns = false;
        _portGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(PortEntry.PortRange), HeaderText = "포트 / 범위", Width = 120, AutoSizeMode = DataGridViewAutoSizeColumnMode.None });
        _portGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(PortEntry.Protocol), HeaderText = "프로토콜", Width = 80, AutoSizeMode = DataGridViewAutoSizeColumnMode.None });
        _portGrid.Columns.Add(new DataGridViewCheckBoxColumn { DataPropertyName = nameof(PortEntry.Active), HeaderText = "차단 선택", Width = 85, AutoSizeMode = DataGridViewAutoSizeColumnMode.None });
        _portGrid.Columns.Add(new DataGridViewCheckBoxColumn { DataPropertyName = nameof(PortEntry.TimeEnabled), HeaderText = "시간 적용", Width = 85, AutoSizeMode = DataGridViewAutoSizeColumnMode.None });
        _portGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(PortEntry.TimeDescription), HeaderText = "시간 설정", AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill });
        _portGrid.Columns.Add(new DataGridViewTextBoxColumn { Name = nameof(PortEntry.CurrentState), DataPropertyName = nameof(PortEntry.CurrentState), HeaderText = "현재 상태", Width = 85, AutoSizeMode = DataGridViewAutoSizeColumnMode.None });
        _portGrid.Columns.Add(new DataGridViewTextBoxColumn { Name = nameof(PortEntry.RemainingTime), DataPropertyName = nameof(PortEntry.RemainingTime), HeaderText = "남은 시간", Width = 190, AutoSizeMode = DataGridViewAutoSizeColumnMode.None, SortMode = DataGridViewColumnSortMode.NotSortable });
        _portGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(PortEntry.CreatedAt), HeaderText = "등록 일시", Width = 150, AutoSizeMode = DataGridViewAutoSizeColumnMode.None, DefaultCellStyle = new DataGridViewCellStyle { Format = "yyyy-MM-dd HH:mm" } });
        _portGrid.CellMouseDoubleClick += (_, e) =>
        {
            if (!_adminUnlocked || e.Button != MouseButtons.Left || e.RowIndex < 0 || e.ColumnIndex < 0) return;
            if (_portGrid.Columns[e.ColumnIndex].DataPropertyName == nameof(PortEntry.TimeEnabled))
            {
                _portGrid.CurrentCell = _portGrid.Rows[e.RowIndex].Cells[e.ColumnIndex];
                EditPortSchedule();
                return;
            }
            if (_portGrid.Columns[e.ColumnIndex].DataPropertyName != nameof(PortEntry.Active)) return;
            if (_portGrid.Rows[e.RowIndex].DataBoundItem is not PortEntry item) return;
            item.Active = !item.Active; SaveAndApplyPorts();
        };
        _portGrid.CellFormatting += (_, e) =>
        {
            if (!_store.Settings.IsAllowAllActive(DateTimeOffset.UtcNow)) return;
            var property = _portGrid.Columns[e.ColumnIndex].DataPropertyName;
            if (property == nameof(PortEntry.CurrentState)) { e.Value = "일시 허용"; e.FormattingApplied = true; }
            if (property == nameof(PortEntry.RemainingTime)) { e.Value = $"허용 종료까지 {ElapsedCountdown.Format(_store.Settings.AllowAllRemaining)}"; e.FormattingApplied = true; }
        };
        var status = new Label { Dock = DockStyle.Bottom, Height = 36, Padding = new Padding(8), ForeColor = Color.DimGray, Text = "‘시간 적용’을 더블클릭하거나 ‘시간 설정’을 눌러 변경하세요. 도메인 또는 포트 중 하나라도 차단이면 접속이 차단됩니다." };
        page.Controls.Add(_portGrid); page.Controls.Add(top); page.Controls.Add(status);
        return page;
    }

    private TabPage BuildHistoryTab()
    {
        var page = new TabPage("접속 기록");
        var export = new Button { Text = "Export", AutoSize = true };
        export.Click += (_, _) => ExportHistory();
        var top = Bar(); _from.Value = DateTime.Today.AddDays(-7); _to.Value = DateTime.Today;
        var query = new Button { Text = "조회", AutoSize = true };
        var collect = _collectAndQueryButton;
        var toolbar = new Panel { Dock = DockStyle.Top };
        var exportArea = new Panel { Dock = DockStyle.Right, Width = export.GetPreferredSize(Size.Empty).Width + 16 };
        export.Location = new Point(8, top.Padding.Top + collect.Margin.Top);
        exportArea.Controls.Add(export);
        top.Dock = DockStyle.Fill;
        toolbar.Controls.Add(top);
        toolbar.Controls.Add(exportArea);
        _collectionButton.Click += async (_, _) => await ToggleCollectionAsync();
        query.Click += (_, _) => RefreshHistory(); collect.Click += async (_, _) => await CollectHistoryAsync(true);
        top.AutoScroll = true;
        _historyStatus.AutoSize = false;
        _historyStatus.TextAlign = ContentAlignment.MiddleLeft;
        _historyStatus.Margin = collect.Margin;
        void AlignHistoryStatus()
        {
            _historyStatus.Size = new Size(TextRenderer.MeasureText(_historyStatus.Text, _historyStatus.Font).Width + 8, collect.Height);
            toolbar.Height = Math.Max(48, collect.Height + top.Padding.Vertical + collect.Margin.Vertical + SystemInformation.HorizontalScrollBarHeight);
        }
        _historyStatus.TextChanged += (_, _) => AlignHistoryStatus();
        collect.SizeChanged += (_, _) => AlignHistoryStatus();
        top.Controls.AddRange([_collectionButton, new Label { Text = "기간", AutoSize = true, Margin = new Padding(3, 8, 3, 0) }, _from, new Label { Text = "~", AutoSize = true, Margin = new Padding(3, 8, 3, 0) }, _to, _search, query, collect, _historyStatus]);
        AlignHistoryStatus();
        _historyGrid.AutoGenerateColumns = false;
        _historyGrid.RowHeadersVisible = false;
        _historyGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = "Index", HeaderText = "번호", Width = 65, AutoSizeMode = DataGridViewAutoSizeColumnMode.None, SortMode = DataGridViewColumnSortMode.NotSortable });
        _historyGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = "VisitedAt", HeaderText = "접속 일시", Width = 145, DefaultCellStyle = new DataGridViewCellStyle { Format = "yyyy-MM-dd HH:mm:ss" } });
        _historyGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = "Browser", HeaderText = "브라우저", Width = 80 });
        _historyGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = "Title", HeaderText = "제목", Width = 280 });
        _historyGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = "Url", HeaderText = "접속 URL", AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill });
        _historyGrid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = "DurationText", HeaderText = "추정 접속시간", Width = 110 });
        page.Controls.Add(_historyGrid); page.Controls.Add(toolbar); page.Controls.Add(BuildHistoryGuide());
        return page;
    }

    private Control BuildHistoryGuide()
    {
        var guide = new TableLayoutPanel { Dock = DockStyle.Top, ColumnCount = 3, RowCount = 1, Padding = new Padding(8), Height = 120 };
        var items = new[]
        {
            (Title: $"자동 수집 · {_collectionTimer.Interval / 1000}초 간격", Body: "앱 실행 시 수집하고, 이후 1분마다 새 기록을 가져옵니다. 수집 완료 후 목록도 갱신됩니다.", Background: Color.FromArgb(239, 246, 255), Accent: Color.FromArgb(29, 78, 216)),
            (Title: "조회 · 클릭할 때 갱신", Body: "저장된 기록에서 선택한 기간과 검색어로 조회합니다. ‘수집 후 조회’는 새 기록부터 가져옵니다.", Background: Color.FromArgb(240, 253, 250), Accent: Color.FromArgb(15, 118, 110)),
            (Title: "중지 · 수집만 잠시 멈춤", Body: "자동·수동 수집을 멈춰도 기존 기록 조회와 Export는 가능합니다. ‘수집 시작’으로 다시 켜세요.", Background: Color.FromArgb(245, 243, 255), Accent: Color.FromArgb(109, 40, 217))
        };
        var labels = new List<(Label Title, Label Body)>();
        for (var i = 0; i < items.Length; i++)
        {
            guide.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f / 3));
            var item = items[i];
            var card = new Panel { Dock = DockStyle.Fill, BackColor = item.Background, Margin = new Padding(4) };
            var title = new Label { Text = item.Title, Font = new Font(Font, FontStyle.Bold), ForeColor = item.Accent, UseMnemonic = false };
            var body = new Label { Text = item.Body, ForeColor = Color.FromArgb(71, 85, 105), UseMnemonic = false };
            card.Controls.AddRange([title, body]);
            guide.Controls.Add(card, i, 0);
            labels.Add((title, body));
        }
        var previousWidth = -1;
        void ResizeGuide()
        {
            if (guide.ClientSize.Width == previousWidth) return;
            previousWidth = guide.ClientSize.Width;
            var width = Math.Max(80, (guide.ClientSize.Width - guide.Padding.Horizontal) / 3 - 8 - 24);
            var height = 0;
            foreach (var (title, body) in labels)
            {
                var flags = TextFormatFlags.WordBreak | TextFormatFlags.TextBoxControl | TextFormatFlags.NoPrefix;
                var titleHeight = TextRenderer.MeasureText(title.Text, title.Font, new Size(width, int.MaxValue), flags).Height + 4;
                var bodyHeight = TextRenderer.MeasureText(body.Text, body.Font, new Size(width, int.MaxValue), flags).Height + 6;
                title.SetBounds(12, 12, width, titleHeight);
                body.SetBounds(12, 18 + titleHeight, width, bodyHeight);
                height = Math.Max(height, 30 + titleHeight + bodyHeight);
            }
            guide.Height = height + guide.Padding.Vertical + 8;
        }
        guide.ClientSizeChanged += (_, _) => ResizeGuide();
        ResizeGuide();
        return guide;
    }

    private async void OnFirstShown(object? sender, EventArgs e)
    {
        if (!_store.HasPassword)
        {
            var password = PasswordDialog.CreatePassword(this);
            if (password is null)
            {
                MessageBox.Show("최초 관리자 비밀번호를 설정해야 사용할 수 있습니다.");
                _allowExit = true; Close(); return;
            }
            _store.SetPassword(password);
            _mobileServer?.RevokeSessions();
            MessageBox.Show("관리자 비밀번호가 설정되었습니다. 분실 시 마스터 비밀번호로 인증하여 초기화할 수 있습니다.", "설정 완료");
        }
        RefreshRules();
        ApplyScheduledDomains(true);
        _domainTimer.Start();
        await StartMessageBridgeAsync();
        await CollectHistoryAsync(false);
        if (_collectionEnabled) _collectionTimer.Start();
    }

    private void ToggleAdmin()
    {
        if (_adminUnlocked) { SetAdminState(false); return; }
        if (PasswordDialog.Verify(this, _store)) SetAdminState(true);
    }

    private void ResetPassword()
    {
        if (!PasswordDialog.Verify(this, _store)) return;
        var password = PasswordDialog.CreatePassword(this, "관리자 비밀번호 초기화");
        if (password is null) return;
        try
        {
            _store.SetPassword(password);
            SetAdminState(false);
            MessageBox.Show(this, "새 관리자 비밀번호가 저장되었습니다. 다시 관리자 인증을 진행하세요.", "초기화 완료");
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, $"비밀번호를 저장하지 못했습니다. 기존 비밀번호가 유지됩니다.\n{ex.Message}", "초기화 실패", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void SetAdminState(bool unlocked)
    {
        if (unlocked && !_tabs.TabPages.Contains(_messagesPage)) _tabs.TabPages.Add(_messagesPage);
        if (!unlocked && _tabs.TabPages.Contains(_messagesPage))
        {
            if (_tabs.SelectedTab == _messagesPage) _tabs.SelectedIndex = 0;
            _tabs.TabPages.Remove(_messagesPage);
        }
        _portEndInput.Enabled = unlocked && _portRangeEnabled.Checked;
        _resetSettingsButton.Visible = unlocked;
        _resetSettingsButton.Enabled = unlocked && !_resettingSettings;
        _autoStartButton.Visible = unlocked;
        _removeAutoStartButton.Visible = unlocked;
        _autoStartFooter.Visible = unlocked;
        _autoStartButton.Enabled = _removeAutoStartButton.Enabled = unlocked && !_autoStartBusy && !_resettingSettings && !_shutdownInProgress;
        _adminUnlocked = unlocked;
        if (unlocked) RefreshMessageDomains();
        _lockState.Text = unlocked ? "  관리자 모드  " : "  잠금 상태  ";
        _lockState.ForeColor = unlocked ? Color.DarkGreen : Color.Firebrick;
        _loginButton.Text = unlocked ? "관리자 잠금" : "관리자 모드";
        _exitButton.Visible = unlocked;
        foreach (Control page in _tabs.TabPages)
            SetTaggedControls(page, unlocked);
        if (!unlocked) _certificatePassword.Clear();
        UpdateMobileControls();
    }

    private async Task ResetSettingsAsync()
    {
        if (!_adminUnlocked || _resettingSettings || _autoStartBusy) return;
        if (_mobileBusy)
        {
            MessageBox.Show(this, "스마트폰 연결 처리가 끝난 뒤 다시 시도하세요.", "설정초기화");
            return;
        }
        if (MessageBox.Show(this,
            "도메인·포트 차단 목록과 시간 설정, 모든 사이트 일시 허용을 초기화합니다.\n스마트폰 연결을 종료하고 자동 수집·조회 조건을 기본값으로 되돌립니다.\n현재 Windows 계정의 재부팅후 자동실행 등록도 해제합니다.\n\n관리자·마스터 비밀번호와 수집된 방문 기록은 유지됩니다.\n설정을 초기화하시겠습니까?",
            "설정초기화 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2) != DialogResult.Yes) return;
        _resettingSettings = true;
        UpdateMobileControls();
        _resetSettingsButton.Enabled = false;
        _autoStartButton.Enabled = _removeAutoStartButton.Enabled = false;
        try
        {
            if (_mobileServer is not null) await StopMobileAsync();
            await AutoStartService.ConfigureAsync(false);
            _store.ResetSettings();
            LoadMobilePreferences();
            _childMessagePopup?.Close(); _messageCooldowns.Clear();
            _domainInput.Clear(); _portInput.Value = 1; _portEndInput.Value = 1; _portRangeEnabled.Checked = false; _protocol.SelectedIndex = 0;
            _from.Value = DateTime.Today.AddDays(-7); _to.Value = DateTime.Today; _search.Clear();
            _collectionEnabled = true;
            _collectionButton.Text = "중지";
            _collectNowButton.Enabled = _collectAndQueryButton.Enabled = true;
            _collectionTimer.Start();
            _appliedDomainSignature = null; _appliedPortSignature = null; _appliedAllowAll = null;
            RefreshRules(); ApplyScheduledDomains(true);
            RefreshLanAddresses(); UpdateAllowanceLabel(); RefreshHistory();
            if (_lastProtectionError is not null)
                MessageBox.Show(this, "설정은 초기화했지만 실제 차단 해제를 완료하지 못했습니다.\nPC의 보호 상태를 확인하세요. 자동으로 다시 시도합니다.", "차단 해제 확인 필요", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            else
                MessageBox.Show(this, "설정을 초기화하고 차단을 해제했습니다.\n비밀번호와 방문 기록은 유지되었습니다.", "설정초기화 완료", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, $"설정초기화 중 오류가 발생했습니다.\n{ex.Message}", "설정초기화 오류", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            _resettingSettings = false;
            UpdateMobileControls();
            _resetSettingsButton.Enabled = _adminUnlocked;
            _autoStartButton.Enabled = _removeAutoStartButton.Enabled = _adminUnlocked && !_autoStartBusy && !_shutdownInProgress;
        }
    }

    private static void SetTaggedControls(Control root, bool enabled)
    {
        foreach (Control child in root.Controls)
        {
            if (Equals(child.Tag, "admin")) child.Enabled = enabled;
            SetTaggedControls(child, enabled);
        }
    }

    private void AddDomain()
    {
        if (!_adminUnlocked) return;
        try
        {
            var domain = BlockingService.NormalizeDomain(_domainInput.Text);
            if (_store.Settings.Domains.Any(x => x.Domain.Equals(domain, StringComparison.OrdinalIgnoreCase))) throw new InvalidOperationException("이미 등록된 도메인입니다.");
            _store.Settings.Domains.Add(new() { Domain = domain }); SaveAndApplyDomains(); _domainInput.Clear();
        }
        catch (Exception ex) { MessageBox.Show(ex.Message, "등록 실패", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
    }

    private void ToggleDomain()
    {
        if (!_adminUnlocked) return;
        if (_domainGrid.CurrentRow?.DataBoundItem is not BlockEntry item) return;
        item.Active = !item.Active; SaveAndApplyDomains();
    }

    private void SetAllDomainsActive(bool active)
    {
        if (!_adminUnlocked || !_store.Settings.Domains.Any(x => x.Active != active)) return;
        foreach (var item in _store.Settings.Domains) item.Active = active;
        SaveAndApplyDomains();
    }

    private void RemoveDomain()
    {
        if (_domainGrid.CurrentRow?.DataBoundItem is not BlockEntry item) return;
        if (MessageBox.Show($"{item.Domain}을 삭제하시겠습니까?", "확인", MessageBoxButtons.YesNo) != DialogResult.Yes) return;
        _store.Settings.Domains.Remove(item); SaveAndApplyDomains();
    }

    private void EditDomainSchedule()
    {
        if (!_adminUnlocked || _domainGrid.CurrentRow?.DataBoundItem is not BlockEntry item) return;
        var version = MobileRules.Version(item);
        using var dialog = new DomainScheduleDialog(item.Domain, item.Schedule);
        if (dialog.ShowDialog(this) != DialogResult.OK || dialog.Result is null) return;
        if (!_store.Settings.Domains.Contains(item) || MobileRules.Version(item) != version)
        {
            MessageBox.Show(this, "편집 중 사이트 설정이 변경되었습니다. 최신 목록에서 다시 편집하세요.", "설정 변경 확인");
            return;
        }
        var previous = item.Schedule;
        item.Schedule = dialog.Result;
        try { _store.Save(); }
        catch (Exception ex)
        {
            item.Schedule = previous;
            MessageBox.Show(this, ex.Message, "시간 설정 저장 실패", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        ApplyScheduledDomains(true);
        RefreshRules();
    }

    private void SaveAndApplyDomains() { _store.Save(); ApplyScheduledDomains(true); RefreshRules(); }

    private void ApplyScheduledDomains(bool force = false)
    {
        var now = DateTimeOffset.UtcNow;
        var allowAll = _store.Settings.IsAllowAllActive(now);
        var domains = allowAll ? [] : _store.Settings.Domains;
        var ports = allowAll ? [] : _store.Settings.Ports;
        var signature = string.Join("\n", domains.Where(x => x.ShouldBlock(now))
            .Select(x => x.Domain).Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(x => x, StringComparer.OrdinalIgnoreCase));
        var portSignature = string.Join("\n", ports.Where(x => x.ShouldBlock(now)).Select(x => $"{x.Protocol}:{x.PortRange}").OrderBy(x => x));
        if (!force && signature == _appliedDomainSignature && portSignature == _appliedPortSignature && allowAll == _appliedAllowAll) return;
        try
        {
            if (force || signature != _appliedDomainSignature)
            {
                BlockingService.ApplyDomains(domains, now);
                _appliedDomainSignature = signature;
            }
            if (portSignature != _appliedPortSignature)
            {
                BlockingService.ApplyPorts(ports, now);
                _appliedPortSignature = portSignature;
            }
            _lastProtectionError = null;
            _appliedAllowAll = allowAll;
            _domainStatus.Text = allowAll ? "모든 사이트 일시 허용 중 · 경과 시간으로 자동 종료"
                : "시간 규칙 적용 중 · 시간 적용을 끄면 수동 차단 상태를 따릅니다.";
            _domainStatus.ForeColor = Color.DimGray;
            _domainGrid.Refresh();
            _portGrid.Refresh();
        }
        catch (Exception ex)
        {
            _appliedDomainSignature = null;
            _appliedPortSignature = null;
            _lastProtectionError = "차단 규칙 적용에 실패했습니다. PC에서 관리자 권한과 보호 상태를 확인하세요.";
            _domainStatus.Text = $"차단 적용 실패 (자동 재시도): {ex.Message}";
            _domainStatus.ForeColor = Color.Firebrick;
        }
        finally { RefreshHostsStatus(true); }
    }

    private void AddPort()
    {
        if (!_adminUnlocked) return;
        var port = (int)_portInput.Value; var protocol = _protocol.Text;
        var item = new PortEntry { Port = port, EndPort = _portRangeEnabled.Checked ? (int)_portEndInput.Value : null, Protocol = protocol };
        try { item.ValidateRange(); }
        catch (ArgumentException ex) { MessageBox.Show(this, ex.Message, "포트 범위 확인", MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
        if (_store.Settings.Ports.Any(x => x.Port == port && x.EffectiveEndPort == item.EffectiveEndPort && x.Protocol == protocol)) { MessageBox.Show("이미 등록된 포트 또는 범위입니다."); return; }
        _store.Settings.Ports.Add(item);
        try { _store.Save(); }
        catch (Exception ex)
        {
            _store.Settings.Ports.Remove(item);
            MessageBox.Show(this, ex.Message, "포트 등록 실패", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        RefreshRules(); ApplyScheduledDomains(true);
    }

    private void TogglePort()
    {
        if (!_adminUnlocked) return;
        if (_portGrid.CurrentRow?.DataBoundItem is not PortEntry item) return;
        item.Active = !item.Active; SaveAndApplyPorts();
    }

    private void RemovePort()
    {
        if (!_adminUnlocked) return;
        if (_portGrid.CurrentRow?.DataBoundItem is not PortEntry item) return;
        if (MessageBox.Show($"{item.Protocol} / {item.PortRange}을 삭제하시겠습니까?", "확인", MessageBoxButtons.YesNo) != DialogResult.Yes) return;
        var index = _store.Settings.Ports.IndexOf(item);
        if (index < 0) return;
        _store.Settings.Ports.RemoveAt(index);
        try { _store.Save(); }
        catch (Exception ex)
        {
            _store.Settings.Ports.Insert(index, item);
            RefreshRules();
            MessageBox.Show(this, $"포트를 삭제하지 못했습니다. 기존 항목을 유지합니다.\n{ex.Message}", "삭제 실패", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        RefreshRules();
        ApplyScheduledDomains(true);
    }

    private void SaveAndApplyPorts() { _store.Save(); RefreshRules(); ApplyScheduledDomains(true); }

    private void SetAllPortsActive(bool active)
    {
        if (!_adminUnlocked || !_store.Settings.Ports.Any(x => x.Active != active)) return;
        foreach (var item in _store.Settings.Ports) item.Active = active;
        SaveAndApplyPorts();
    }

    private void EditPortSchedule()
    {
        if (!_adminUnlocked || _portGrid.CurrentRow?.DataBoundItem is not PortEntry item) return;
        using var dialog = new DomainScheduleDialog($"{item.Protocol} / {item.PortRange}", item.Schedule);
        if (dialog.ShowDialog(this) != DialogResult.OK || dialog.Result is null) return;
        var previous = item.Schedule;
        item.Schedule = dialog.Result;
        try { _store.Save(); }
        catch (Exception ex)
        {
            item.Schedule = previous;
            MessageBox.Show(this, ex.Message, "시간 설정 저장 실패", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        ApplyScheduledDomains(true); RefreshRules();
    }

    private void RefreshRules()
    {
        // List<T> does not notify the grid about removals. Bind a snapshot so a repaint
        // cannot access a removed index before the next explicit refresh.
        _domainGrid.DataSource = null; _domainGrid.DataSource = _store.Settings.Domains.ToList();
        _portGrid.DataSource = null; _portGrid.DataSource = _store.Settings.Ports.ToList();
        RefreshMessageDomains();
    }

    private void ExportHistory()
    {
        if (_historyGrid.Rows.Count == 0)
        {
            MessageBox.Show(this, "내보낼 접속 기록이 없습니다. 기간을 선택하고 조회하세요.", "Export");
            return;
        }
        using var dialog = new SaveFileDialog
        {
            Title = "현재 조회된 접속 기록 내보내기",
            Filter = "Excel 통합 문서 (*.xlsx)|*.xlsx|CSV 파일 (*.csv)|*.csv",
            FileName = $"접속기록_{DateTime.Now:yyyyMMdd_HHmmss}",
            AddExtension = true, OverwritePrompt = true
        };
        if (dialog.ShowDialog(this) != DialogResult.OK) return;
        try
        {
            var columns = _historyGrid.Columns.Cast<DataGridViewColumn>()
                .Where(x => x.Visible).OrderBy(x => x.DisplayIndex).ToArray();
            var rows = new List<string[]> { columns.Select(x => x.HeaderText).ToArray() };
            rows.AddRange(_historyGrid.Rows.Cast<DataGridViewRow>().Where(x => !x.IsNewRow)
                .Select(row => columns.Select(column => row.Cells[column.Index].FormattedValue?.ToString() ?? "").ToArray()));
            HistoryExport.Save(dialog.FileName, rows);
            MessageBox.Show(this, $"접속 기록 {rows.Count - 1:N0}건을 저장했습니다.\n{dialog.FileName}", "Export 완료");
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, $"파일을 저장하지 못했습니다.\n{ex.Message}", "Export 실패", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async Task ToggleCollectionAsync()
    {
        _collectionEnabled = !_collectionEnabled;
        _collectionButton.Text = _collectionEnabled ? "중지" : "수집 시작";
        _collectNowButton.Enabled = _collectAndQueryButton.Enabled = _collectionEnabled;
        if (!_collectionEnabled)
        {
            _collectionTimer.Stop();
            _collectionCancellation?.Cancel();
            _historyStatus.Text = "수집 중지됨";
            return;
        }
        _collectionTimer.Start();
        await CollectHistoryAsync(false);
    }

    private async Task CollectHistoryAsync(bool notify)
    {
        if (!_collectionEnabled || _collectionCancellation is not null) return;
        using var cancellation = new CancellationTokenSource();
        _collectionCancellation = cancellation;
        try
        {
            _historyStatus.Text = "수집 중...";
            var count = await Task.Run(() => _history.CollectAsync(cancellation.Token));
            cancellation.Token.ThrowIfCancellationRequested();
            if (IsDisposed) return;
            RefreshHistory();
            _historyStatus.Text = $"신규 {count:N0}건 · {DateTime.Now:HH:mm:ss}";
            if (notify) MessageBox.Show($"새 방문 기록 {count:N0}건을 저장했습니다.", "수집 완료");
        }
        catch (OperationCanceledException) { if (!IsDisposed) _historyStatus.Text = _collectionEnabled ? "수집 대기 중" : "수집 중지됨"; }
        catch (Exception ex) { if (!IsDisposed) { _historyStatus.Text = "수집 오류"; if (notify) MessageBox.Show(ex.Message); } }
        finally { _collectionCancellation = null; }
    }

    private void RefreshHistory()
    {
        var rows = _history.Read(_from.Value.Date, _to.Value.Date.AddDays(1), _search.Text.Trim())
            .OrderByDescending(x => x.VisitedAt)
            .Select((x, index) => new { Index = index + 1, x.VisitedAt, x.Browser, x.Title, x.Url, DurationText = x.DurationSeconds == 0 ? "-" : TimeSpan.FromSeconds(x.DurationSeconds).ToString(@"mm\:ss") }).ToList();
        _historyGrid.DataSource = rows; _historyStatus.Text = $"{rows.Count:N0}건" + (_collectionEnabled ? "" : " · 수집 중지됨");
    }

    private void ConfigureTray()
    {
        var menu = new ContextMenuStrip();
        menu.Items.Add("Safe Child 열기", null, (_, _) => RestoreFromTray());
        menu.Items.Add("관리자 인증 후 종료", null, (_, _) => AdminExit());
        _tray.Icon = SystemIcons.Shield; _tray.Text = "Safe Child - 보호 실행 중"; _tray.ContextMenuStrip = menu; _tray.Visible = true;
        _tray.DoubleClick += (_, _) => RestoreFromTray();
    }

    private void HideToTray() { Hide(); ShowInTaskbar = false; _tray.ShowBalloonTip(1500, "Safe Child", "보호 기능이 트레이에서 계속 실행됩니다.", ToolTipIcon.Info); }
    private void RestoreFromTray() { ShowInTaskbar = true; Show(); WindowState = FormWindowState.Normal; Activate(); }
    private void AdminExit() { if (!_adminUnlocked && !PasswordDialog.Verify(this, _store)) return; _allowExit = true; Close(); }
    private void SaveTimerCheckpoint()
    {
        var ticks = Environment.TickCount64;
        if (ticks - _lastTimerCheckpoint < 5000) return;
        _lastTimerCheckpoint = ticks;
        try { _store.Save(); }
        catch
        {
            // Do not continue a permissive override when recovery state cannot be saved.
            _store.Settings.AllowAllCountdown = null;
            _store.Settings.AllowAllUntil = null;
            _domainStatus.Text = "남은 시간 저장 실패 · 일시 허용을 종료합니다. 저장 폴더 권한을 확인하세요.";
        }
    }

    private void OnSessionEnding(object? sender, SessionEndingEventArgs e) => _allowExit = true;
    private async void OnFormClosing(object? sender, FormClosingEventArgs e)
    {
        if (_shutdownComplete) return;
        if (e.CloseReason == CloseReason.WindowsShutDown)
        {
            _shutdownInProgress = true;
            _collectionTimer.Stop(); _domainTimer.Stop();
            _store.Settings.AllowAllCountdown = null;
            _store.Settings.AllowAllUntil = null;
            try { _store.Save(); } catch { }
            ApplyScheduledDomains(true);
            _tray.Visible = false;
            return;
        }
        if (_shutdownInProgress) { e.Cancel = true; return; }
        if (_allowExit)
        {
            e.Cancel = true;
            _shutdownInProgress = true;
            _collectionTimer.Stop(); _domainTimer.Stop();
            _collectionCancellation?.Cancel();
            _exitButton.Text = "종료 중…";
            Enabled = false;
            try
            {
            // Let ongoing startup/stop operations finish while the UI still pumps callbacks.
            while (_startingMessageBridge || _mobileBusy || _resettingSettings || _autoStartBusy) await Task.Delay(50);
            _store.Settings.AllowAllCountdown = null;
            _store.Settings.AllowAllUntil = null;
            try { _store.Save(); } catch { /* The last periodic checkpoint remains available. */ }
            if (_messageBridge is { } bridge)
            {
                _messageBridge = null;
                try { await bridge.DisposeAsync(); } catch { }
            }
            if (_mobileServer is { } server)
            {
                _mobileServer = null;
                try { await server.DisposeAsync(); } catch { }
                try { await MobileFirewall.RemoveAsync(); } catch { }
            }
            var domains = _store.Settings.Domains.ToList();
            var ports = _store.Settings.Ports.ToList();
            var now = DateTimeOffset.UtcNow;
            await Task.Run(() =>
            {
                // Restore protection after revoking temporary allowance without blocking the UI.
                BlockingService.ApplyDomains(domains, now);
                BlockingService.ApplyPorts(ports, now);
            });
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, $"종료 전 차단 규칙 적용에 실패했습니다.\n{ex.Message}", "종료 처리 안내", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finally
            {
                _tray.Visible = false;
                _shutdownComplete = true;
                Close();
            }
            return;
        }
        e.Cancel = true; HideToTray();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _collectionCancellation?.Cancel(); _collectionTimer.Dispose(); _domainTimer.Dispose();
            if (_messageBridge is { } bridge)
            {
                _ = Task.Run(async () => { try { await bridge.DisposeAsync(); } catch { } });
                _messageBridge = null;
            }
            _childMessagePopup?.Close(); _messagesPage?.Dispose();
            if (_mobileServer is { } server)
            {
                _ = Task.Run(async () =>
                {
                    try { await server.DisposeAsync(); } catch { }
                    try { await MobileFirewall.RemoveAsync(); } catch { }
                });
                _mobileServer = null;
            }
            _mobileQr.Image?.Dispose();
            _tray.Dispose(); SystemEvents.SessionEnding -= OnSessionEnding;
        }
        base.Dispose(disposing);
    }

    private static FlowLayoutPanel Bar() => new() { Dock = DockStyle.Top, Height = 48, Padding = new Padding(8), WrapContents = false };
    private static DataGridView Grid() => new() { Dock = DockStyle.Fill, ReadOnly = true, AllowUserToAddRows = false, AllowUserToDeleteRows = false, SelectionMode = DataGridViewSelectionMode.FullRowSelect, MultiSelect = false, AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill, BackgroundColor = Color.White };
}

internal static class PasswordDialog
{
    public static bool Verify(IWin32Window owner, SettingsStore store)
    {
        var value = Prompt(owner, "관리자 인증", "관리자 또는 마스터 비밀번호", false);
        if (value is null) return false;
        if (store.VerifyPassword(value)) return true;
        MessageBox.Show(owner, "비밀번호가 올바르지 않습니다.", "인증 실패", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        return false;
    }

    public static string? CreatePassword(IWin32Window owner, string title = "최초 관리자 설정")
    {
        while (true)
        {
            var first = Prompt(owner, title, "새 비밀번호 (8자 이상)", false);
            if (first is null) return null;
            var second = Prompt(owner, title, "비밀번호 확인", false);
            if (second is null) return null;
            if (first.Length >= 8 && first == second) return first;
            MessageBox.Show(owner, "8자 이상의 동일한 비밀번호를 두 번 입력하세요.", "확인 필요");
        }
    }

    private static string? Prompt(IWin32Window owner, string title, string label, bool unused)
    {
        using var dialog = new Form { Text = title, StartPosition = FormStartPosition.CenterParent, FormBorderStyle = FormBorderStyle.FixedDialog, MinimizeBox = false, MaximizeBox = false, ClientSize = new Size(360, 135), ShowInTaskbar = false };
        var text = new TextBox { Left = 20, Top = 45, Width = 280, UseSystemPasswordChar = true, TabIndex = 0 };
        var visibility = new Button
        {
            Left = 306, Top = 42, Width = 34, Height = 28, FlatStyle = FlatStyle.Flat,
            BackColor = dialog.BackColor, Cursor = Cursors.Hand,
            AccessibleName = "비밀번호 표시", TabIndex = 1
        };
        visibility.FlatAppearance.BorderSize = 0;
        visibility.FlatAppearance.MouseOverBackColor = dialog.BackColor;
        visibility.FlatAppearance.MouseDownBackColor = dialog.BackColor;
        var eyeHovered = false;
        visibility.MouseEnter += (_, _) => { eyeHovered = true; visibility.Invalidate(); };
        visibility.MouseLeave += (_, _) => { eyeHovered = false; visibility.Invalidate(); };
        using var tooltip = new ToolTip();
        tooltip.SetToolTip(visibility, "비밀번호 표시");
        visibility.Paint += (_, e) =>
        {
            e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            var x = visibility.ClientSize.Width / 2f;
            var y = visibility.ClientSize.Height / 2f;
            using var background = new SolidBrush(eyeHovered ? Color.FromArgb(219, 234, 254) : Color.FromArgb(239, 244, 251));
            e.Graphics.FillEllipse(background, x - 13, y - 13, 26, 26);
            using var pen = new Pen(eyeHovered ? Color.FromArgb(59, 110, 190) : Color.FromArgb(112, 133, 163), 1.6f)
            {
                StartCap = System.Drawing.Drawing2D.LineCap.Round,
                EndCap = System.Drawing.Drawing2D.LineCap.Round,
                LineJoin = System.Drawing.Drawing2D.LineJoin.Round
            };
            using var eye = new System.Drawing.Drawing2D.GraphicsPath();
            if (text.UseSystemPasswordChar)
            {
                eye.AddBezier(x - 8, y, x - 4, y - 6.5f, x + 4, y - 6.5f, x + 8, y);
                eye.AddBezier(x + 8, y, x + 4, y + 6.5f, x - 4, y + 6.5f, x - 8, y);
                e.Graphics.DrawPath(pen, eye);
                e.Graphics.DrawEllipse(pen, x - 2.4f, y - 2.4f, 4.8f, 4.8f);
            }
            else
            {
                eye.AddBezier(x - 8, y - 2, x - 4, y + 5, x + 4, y + 5, x + 8, y - 2);
                e.Graphics.DrawPath(pen, eye);
                e.Graphics.DrawLine(pen, x - 5.5f, y + 1, x - 7, y + 3.5f);
                e.Graphics.DrawLine(pen, x, y + 3, x, y + 5.5f);
                e.Graphics.DrawLine(pen, x + 5.5f, y + 1, x + 7, y + 3.5f);
            }
        };
        visibility.Click += (_, _) =>
        {
            var selectionStart = text.SelectionStart;
            var selectionLength = text.SelectionLength;
            text.UseSystemPasswordChar = !text.UseSystemPasswordChar;
            visibility.AccessibleName = text.UseSystemPasswordChar ? "비밀번호 표시" : "비밀번호 숨기기";
            tooltip.SetToolTip(visibility, visibility.AccessibleName);
            visibility.Invalidate();
            text.Focus();
            text.Select(selectionStart, selectionLength);
        };
        var ok = new Button { Text = "확인", Left = 180, Top = 85, Width = 75, DialogResult = DialogResult.OK };
        var cancel = new Button { Text = "취소", Left = 265, Top = 85, Width = 75, DialogResult = DialogResult.Cancel };
        dialog.Controls.AddRange([new Label { Text = label, Left = 20, Top = 18, AutoSize = true }, text, visibility, ok, cancel]);
        dialog.AcceptButton = ok; dialog.CancelButton = cancel;
        return dialog.ShowDialog(owner) == DialogResult.OK ? text.Text : null;
    }
}
