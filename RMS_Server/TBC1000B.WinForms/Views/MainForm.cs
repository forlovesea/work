using System.Diagnostics;
using System.Net.Sockets;
using System.Media;
using TBC1000B.WinForms.Models;
using TBC1000B.WinForms.Services;

namespace TBC1000B.WinForms.Views;

public sealed class MainForm : Form
{
    private readonly IMonitorService _service;
    private readonly Profile _profile;
    private readonly ProfileStore _profileStore;
    private readonly OperationRecordService _operationRecorder;
    private readonly TrapLogService _trapLogger;
    private readonly SlaveCoordinator _slaveCoordinator = new();
    private readonly CancellationTokenSource _lifetime = new();
    private readonly string _mode;
    private readonly TextBox _ip = new() { Text = "192.168.0.10", Width = 110 };
    private readonly TextBox _port = new() { Text = "161", Width = 50 };
    private readonly TextBox _get = new() { Text = "sktlfp48r", Width = 80 };
    private readonly TextBox _set = new() { Text = "sktlfp48w", Width = 80 };
    private readonly TextBox _trap = new() { Text = "sktlfp48r", Width = 80 };
    private readonly TextBox _trapPort = new() { Text = "162", Width = 50 };
    private readonly Button _connect = UiTheme.Button("접속시작");
    private readonly Label _connectionDot = new() { Text = "●", AutoSize = true, ForeColor = Color.Gray, Font = new Font("맑은 고딕", 14F) };
    private readonly Label _timeout = new() { Text = "Timeout : 0 / 0", AutoSize = true, ForeColor = Color.DarkViolet, Margin = new Padding(4, 7, 4, 0) };
    private readonly Label _resource = new() { AutoSize = false, TextAlign = ContentAlignment.MiddleLeft, BackColor = Color.FromArgb(31, 31, 31), ForeColor = Color.White, Font = new Font("Consolas", 9F, FontStyle.Bold) };
    private readonly Label _updated = new() { Text = "최종업데이트시간 : 대기중", AutoSize = true, Margin = new Padding(8, 7, 0, 0) };
    private readonly DataGridView _summary = new();
    private readonly TableLayoutPanel _fullEpoPanel = new() { Margin = Padding.Empty, Padding = new Padding(1), ColumnCount = 2, RowCount = 1, BackColor = Color.White };
    private readonly Button _fullCutoffButton = UiTheme.Button("차단", UiTheme.Critical);
    private readonly Button _fullRestoreButton = UiTheme.Button("복구", Color.FromArgb(20, 184, 166));
    private static readonly IReadOnlyDictionary<string, (int Row, int Column)> SummaryPositions = new Dictionary<string, (int, int)>
    {
        ["Rack 전압[V]"] = (3, 0), ["SOC 충전율[%]"] = (3, 1), ["Max 전압[V]"] = (3, 2),
        ["Min 전압[V]"] = (3, 3), ["Avg 전압[V]"] = (3, 4), ["Rack 전류[A]"] = (5, 0),
        ["방전 횟수"] = (5, 1), ["Max 온도[℃]"] = (5, 2), ["Min 온도[℃]"] = (5, 3),
        ["Avg 온도[℃]"] = (5, 4), ["과전압 충전차단"] = (7, 0), ["고온 충전차단"] = (7, 1),
        ["과전류 충전차단"] = (7, 2), ["차단기 OFF"] = (7, 3), ["충전전류제한[C]"] = (7, 4), ["SOC충전제한[%]"] = (7, 5)
    };
    private readonly GroupBox _summaryGroup = new() { Text = "시스템 요약 정보", Dock = DockStyle.Fill };
    private readonly DataGridView _trapGrid = new();
    private readonly DataGridView[] _moduleGrids = [new(), new()];
    private readonly DataGridView _faultGrid = new();
    private readonly TableLayoutPanel _orderList = new();
    private readonly Button _soundButton = UiTheme.Button("🔇");
    private readonly Button _activeAlarmButton = UiTheme.Button("발생된 알람 보기");
    private readonly System.Windows.Forms.Timer _alarmBlinkTimer = new() { Interval = 500 };
    private bool _alarmBlinkOn;
    private readonly System.Windows.Forms.Timer _moduleOrderBlinkTimer = new() { Interval = 500 };
    private bool _moduleOrderBlinkOn;
    private readonly SoundPlayer? _alarmPlayer;
    private bool _alarmPlaying;
    private readonly System.Windows.Forms.Timer _resourceTimer = new() { Interval = 1000 };
    private DateTime _lastCpuSampleAt;
    private TimeSpan _lastCpuTime;
    private IReadOnlyList<ModuleState> _modules = Enumerable.Range(1, 10).Select(n => new ModuleState { Number = n }).ToList();
    private MonitorSnapshot? _latestSnapshot;
    private bool _slaveStarted;
    private bool _ownsMasterMarker;
    private readonly string _masterMarkerPath;
    private bool _fullEpoOperationActive;
    private bool _timeoutWarningShown, _timeoutDisconnectedShown;
    private readonly HashSet<string> _dismissedFaults = new(StringComparer.OrdinalIgnoreCase);
    private Form? _connectionProgress;
    private Label? _connectionProgressText;

    public MainForm(string mode, Profile profile, IMonitorService? service = null)
    {
        _mode = mode;
        _profile = profile;
        _profileStore = new ProfileStore(Path.GetDirectoryName(profile.FilePath)!);
        _masterMarkerPath = Path.Combine(Path.GetDirectoryName(profile.FilePath)!, "master_profile.txt");
        _operationRecorder = new OperationRecordService(Path.Combine(Environment.CurrentDirectory, "Operation data record"));
        _trapLogger = new TrapLogService(Path.Combine(Environment.CurrentDirectory, "Trap logs"), profile.FilePath);
        var alarmPath = Path.Combine(AppContext.BaseDirectory, "Assets", "alarm.wav"); if (File.Exists(alarmPath)) _alarmPlayer = new SoundPlayer(alarmPath);
        _operationRecorder.Error += (_, message) => BeginInvoke(() => MessageBox.Show(this, message, "운전 데이터 기록 오류", MessageBoxButtons.OK, MessageBoxIcon.Error));
        _service = service ?? new SnmpMonitorService();
        if (_mode.Equals("Master", StringComparison.OrdinalIgnoreCase))
        {
            try { _slaveCoordinator.StartMaster(_lifetime.Token); File.WriteAllText(_masterMarkerPath, Path.GetFullPath(_profile.FilePath)); _ownsMasterMarker = true; }
            catch (Exception ex) when (ex is SocketException or IOException or UnauthorizedAccessException)
            {
                _slaveCoordinator.Stop(); _mode = "Slave";
                MessageBox.Show(this, $"Master 등록을 시작할 수 없어 Slave 모드로 전환합니다.\n{ex.Message}", "Master 시작 오류", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }
        var version = typeof(MainForm).Assembly.GetName().Version?.ToString(3) ?? "3.2.4";
        Text = $"TBC1000B-NDA1/IoT Gateway Battery Monitoring System(Base SNMPv2) v{version}  ({_mode.ToUpperInvariant()})";
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        StartPosition = FormStartPosition.CenterScreen;
        WindowState = FormWindowState.Maximized;
        MinimumSize = new Size(1200, 800);
        Font = new Font("맑은 고딕", 8.5F);

        ApplyProfile();
        BuildUi();
        PopulateStaticRows();
        _service.SnapshotChanged += OnSnapshotChanged;
        _service.TrapReceived += OnTrapReceived;
        _service.RawTrapReceived += async (_, trap) => { if (_mode.Equals("Master", StringComparison.OrdinalIgnoreCase)) await _slaveCoordinator.ForwardAsync(trap); };
        _service.TrapListenerFailed += (_, error) => BeginInvoke(() => ShowTrapListenerFailure(error));
        _slaveCoordinator.ForwardedTrapReceived += (_, trap) => OnTrapReceived(this, TrapDataParser.Parse(trap));
        _connect.Click += ToggleConnectionAsync;
        _resourceTimer.Tick += (_, _) => UpdateResourceLabel();
        _resourceTimer.Start();
        _alarmBlinkTimer.Tick += (_, _) => { _alarmBlinkOn = !_alarmBlinkOn; ApplyActiveAlarmButtonStyle(_alarmBlinkOn); };
        _moduleOrderBlinkTimer.Tick += (_, _) => { _moduleOrderBlinkOn = !_moduleOrderBlinkOn; UpdateOrderView(); };
        _moduleOrderBlinkTimer.Start();
        FormClosing += OnFormClosingAsync;
    }

    private void ApplyProfile()
    {
        _ip.Text = _profile.Address; _port.Text = _profile.Port.ToString(); _get.Text = _profile.GetCommunity;
        _set.Text = _profile.SetCommunity; _trap.Text = _profile.TrapCommunity;
        _trapPort.Text = _mode.Equals("Slave", StringComparison.OrdinalIgnoreCase)
            ? (_profile.LocalTrapPort is >= SlaveCoordinator.MinLocalPort and <= SlaveCoordinator.MaxLocalPort ? _profile.LocalTrapPort : 0).ToString()
            : _profile.TrapPort.ToString();
    }

    private void BuildUi()
    {
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(6), RowCount = 5, ColumnCount = 1 };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 88));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 112));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 27));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 48));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 25));
        Controls.Add(root);
        root.Controls.Add(CreateConnectionPanel(), 0, 0);
        root.Controls.Add(CreateHeaderPanel(), 0, 1);
        root.Controls.Add(CreateSummaryTrapPanel(), 0, 2);
        root.Controls.Add(CreateModulesPanel(), 0, 3);
        root.Controls.Add(CreateFaultPanel(), 0, 4);
    }

    private Control CreateConnectionPanel()
    {
        var group = new GroupBox { Text = "축전지 시스템 접속 설정", Dock = DockStyle.Fill };
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, Margin = Padding.Empty, Padding = Padding.Empty };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); layout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); group.Controls.Add(layout);
        var flow = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(5, 10, 5, 2), WrapContents = false, AutoScroll = true, Margin = Padding.Empty };
        layout.Controls.Add(flow, 0, 0);
        AddPair(flow, "IP", _ip); AddPair(flow, "Port", _port); AddPair(flow, "GET", _get);
        AddPair(flow, "SET", _set); AddPair(flow, "TRAP", _trap); AddPair(flow, "TRAP Port", _trapPort);
        _connect.Width = 80; flow.Controls.Add(_connect);
        flow.Controls.Add(new Label { Text = "접속상태", AutoSize = true, Margin = new Padding(12, 7, 2, 0) });
        flow.Controls.Add(_connectionDot); flow.Controls.Add(_timeout);
        foreach (var item in new[] { ("CRIT", 1), ("MAJOR", 2), ("MINOR", 3), ("WARN", 4) }) { var check = new CheckBox { Text = item.Item1, Checked = _profile.AlarmLevels.GetValueOrDefault(item.Item2), AutoSize = true, Margin = new Padding(8, 6, 0, 0) }; check.CheckedChanged += (_, _) => { _profile.AlarmLevels[item.Item2] = check.Checked; _profileStore.Save(_profile); UpdateAlarmSound(_latestSnapshot); }; flow.Controls.Add(check); }
        _soundButton.Width = 34; _soundButton.Height = 27; _soundButton.Text = SoundText(); _soundButton.Click += (_, _) => { _profile.AlarmVolume = (_profile.AlarmVolume + 1) % 4; _soundButton.Text = SoundText(); _profileStore.Save(_profile); UpdateAlarmSound(_latestSnapshot); }; flow.Controls.Add(_soundButton);
        var order = UiTheme.Button("모듈 설치 순서 설정", UiTheme.Accent); order.Width = 128;
        order.Click += (_, _) => { using var dialog = new ModuleOrderDialog(_profile, _profileStore, _modules); if (dialog.ShowDialog(this) == DialogResult.OK) UpdateOrderView(); }; flow.Controls.Add(order);
        var logos = new FlowLayoutPanel { AutoSize = true, Anchor = AnchorStyles.Top | AnchorStyles.Right, WrapContents = false, Margin = Padding.Empty, Padding = new Padding(3, 0, 5, 0) };
        AddLogo(logos, "skt_logo.png", 100, 45); AddLogo(logos, "pantech.png", 120, 45); layout.Controls.Add(logos, 1, 0);
        return group;
    }

    private Control CreateHeaderPanel()
    {
        var group = new GroupBox { Dock = DockStyle.Fill };
        var table = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, ColumnCount = 1 };
        table.RowStyles.Add(new RowStyle(SizeType.Percent, 50)); table.RowStyles.Add(new RowStyle(SizeType.Percent, 50)); group.Controls.Add(table);
        var top = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
        AddPair(top, "설치 장소", new TextBox { Text = _profile.Site, Width = 180 });
        AddPair(top, "축전지명", new TextBox { Text = _profile.SystemName, Width = 250 });
        var slaves = UiTheme.Button("Slave 목록"); slaves.Width = 112; slaves.MinimumSize = new Size(112, 32); slaves.Height = 32; slaves.Padding = Padding.Empty; slaves.Margin = new Padding(3, 1, 3, 7); slaves.Visible = _mode.Equals("Master", StringComparison.OrdinalIgnoreCase); slaves.Click += (_, _) => new SlaveListDialog(_slaveCoordinator).ShowDialog(this); top.Controls.Add(slaves);
        _activeAlarmButton.Width = 190; _activeAlarmButton.MinimumSize = new Size(190, 32); _activeAlarmButton.Height = 32; _activeAlarmButton.Padding = Padding.Empty; _activeAlarmButton.Margin = new Padding(3, 1, 3, 7); _activeAlarmButton.Enabled = false; _activeAlarmButton.Font = new Font("맑은 고딕", 8.5F, FontStyle.Bold); _activeAlarmButton.Click += (_, _) => new ActiveAlarmDialog(_latestSnapshot?.ActiveAlarms).Show(this); ApplyActiveAlarmButtonStyle(false); top.Controls.Add(_activeAlarmButton);
        var list = UiTheme.Button("※ 정의된 알람 리스트", Color.FromArgb(96, 210, 187)); list.Width = 205; list.MinimumSize = new Size(205, 32); list.Height = 32; list.Padding = Padding.Empty; list.Margin = new Padding(3, 1, 3, 7); list.Click += (_, _) => new AlarmDefinitionDialog().Show(this); top.Controls.Add(list);
        _resource.Width = 530; _resource.Height = 32; _resource.Margin = new Padding(25, 0, 0, 0); top.Controls.Add(_resource);
        var bottom = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
        AddPair(bottom, "설비번호", new TextBox { Width = 120 }); AddPair(bottom, "운용 관리자", new TextBox { Width = 120 });
        AddPair(bottom, "제조사", new TextBox { Width = 120 }); AddPair(bottom, "모델명", new TextBox { Width = 120 }); AddPair(bottom, "상면", new TextBox { Width = 140 });
        var save = UiTheme.Button("저장"); save.Width = 60; bottom.Controls.Add(save);
        bottom.Controls.Add(new Label { Text = "TX ●   RX ●", ForeColor = Color.DimGray, AutoSize = true, Margin = new Padding(10, 7, 0, 0) });
        bottom.Controls.Add(_updated);
        table.Controls.Add(top, 0, 0); table.Controls.Add(bottom, 0, 1);
        return group;
    }

    private Control CreateSummaryTrapPanel()
    {
        var split = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
        split.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 38)); split.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 62));
        UiTheme.ConfigureGrid(_summary); _summary.Dock = DockStyle.Fill; _summary.ReadOnly = true; _summary.ColumnCount = 6; _summary.RowCount = 8;
        _summary.CellClick += async (_, e) => { if (e.RowIndex == 7 && e.ColumnIndex == 4) await OpenChargeLimitAsync(); else if (e.RowIndex == 7 && e.ColumnIndex == 5) await OpenSocLimitAsync(); };
        ConfigureFullEpoButtons();
        _summaryGroup.Controls.Add(_summary); split.Controls.Add(_summaryGroup, 0, 0);
        var trapGroup = new Panel { Dock = DockStyle.Fill, BorderStyle = BorderStyle.FixedSingle };
        var trapLayout = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 3, Padding = new Padding(3) }; trapLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 38)); trapLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); trapLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
        var trapHeader = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = Padding.Empty, WrapContents = false };
        trapHeader.Controls.Add(new Label { Text = "SNMP Trap 로그", AutoSize = true, Font = new Font("맑은 고딕", 9F, FontStyle.Bold), Margin = new Padding(3, 9, 4, 0) });
        trapHeader.Controls.Add(new Label { Text = "(최대 1000개 저장)", AutoSize = true, ForeColor = Color.DimGray, Margin = new Padding(0, 10, 9, 0) });
        var retransmit = UiTheme.Button("재전송요청", Color.FromArgb(96, 210, 187)); retransmit.Width = 120; retransmit.MinimumSize = new Size(120, 31); retransmit.Height = 31; retransmit.AutoEllipsis = false; retransmit.Padding = Padding.Empty; retransmit.Margin = new Padding(0, 3, 7, 0); retransmit.Click += async (_, _) => await RequestTrapRetransmitAsync(retransmit); trapHeader.Controls.Add(retransmit);
        UiTheme.ConfigureGrid(_trapGrid); _trapGrid.Dock = DockStyle.Fill; _trapGrid.ReadOnly = true;
        foreach (var h in new[] { "시간", "Trap OID", "OrdinalNumber", "Alarm", "Level", "EquipID", "EquipName", "FatherEquip" }) _trapGrid.Columns.Add(h, h);
        _trapGrid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        var clear = UiTheme.Button("TRAP 로그 전체 삭제", UiTheme.Accent); clear.Dock = DockStyle.Fill; clear.Click += (_, _) => _trapGrid.Rows.Clear();
        trapLayout.Controls.Add(trapHeader, 0, 0); trapLayout.Controls.Add(_trapGrid, 0, 1); trapLayout.Controls.Add(clear, 0, 2); trapGroup.Controls.Add(trapLayout); split.Controls.Add(trapGroup, 1, 0);
        return split;
    }

    private Control CreateModulesPanel()
    {
        var group = new GroupBox { Text = "모듈 상태", Dock = DockStyle.Fill };
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, ColumnCount = 2 };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 42)); root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 80)); root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 20)); group.Controls.Add(root);
        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(0, 2, 0, 2), WrapContents = false, Margin = Padding.Empty };
        var reset = UiTheme.Button("상태 초기화", Color.FromArgb(232, 84, 77)); reset.Width = 118; reset.MinimumSize = new Size(118, 32); reset.Click += (_, _) => ResetModuleState(); actions.Controls.Add(reset);
        var record = UiTheme.Button("운전 데이타 기록", Color.FromArgb(41, 111, 215)); record.Width = 165; record.MinimumSize = new Size(165, 32); record.Click += (_, _) => new OperationRecordDialog(_operationRecorder, () => _latestSnapshot).ShowDialog(this); actions.Controls.Add(record);
        var all = UiTheme.Button("전체모듈정보", Color.Teal); all.Width = 142; all.MinimumSize = new Size(142, 32); all.Click += (_, _) => new AllModulesDialog(_modules).Show(this); actions.Controls.Add(all);
        foreach (var button in actions.Controls.OfType<Button>()) button.MinimumSize = Size.Empty;
        reset.Width = 105; record.Width = 145; all.Width = 125;
        foreach (var button in actions.Controls.OfType<Button>()) { button.Height = 32; button.MinimumSize = new Size(button.Width, 32); button.Padding = Padding.Empty; button.Margin = new Padding(3, 2, 3, 2); }
        actions.Controls.Add(new Label { Text = "※ 경보 색상 기준:", AutoSize = true, Margin = new Padding(18, 10, 3, 0) });
        actions.Controls.Add(UiTheme.LegendChip("Critical", UiTheme.Critical, Color.White));
        actions.Controls.Add(UiTheme.LegendChip("Major", UiTheme.Major, Color.White));
        actions.Controls.Add(UiTheme.LegendChip("Minor", UiTheme.Minor, Color.Black));
        actions.Controls.Add(UiTheme.LegendChip("Warning", UiTheme.Warning, Color.Black));
        root.Controls.Add(actions, 0, 0);
        var grids = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 }; grids.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50)); grids.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        for (var i = 0; i < 2; i++) { ConfigureModuleGrid(_moduleGrids[i], i * 5 + 1); grids.Controls.Add(_moduleGrids[i], i, 0); }
        root.Controls.Add(grids, 0, 1);
        var orderGroup = new GroupBox { Text = "모듈 설치 순서", Dock = DockStyle.Fill, Padding = new Padding(7, 5, 7, 7), Font = new Font("맑은 고딕", 9F, FontStyle.Bold) };
        var orderLayout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2, Margin = Padding.Empty, Padding = Padding.Empty };
        orderLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 36)); orderLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        var legend = new Label
        {
            Text = "● 빨간색: 알람발생    ● 회색: 차단(Disconnect)\r\n● 깜박임: 바코드 불일치",
            Dock = DockStyle.Fill,
            ForeColor = Color.FromArgb(75, 85, 99),
            Font = new Font("맑은 고딕", 7.5F, FontStyle.Regular),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(3, 0, 0, 0),
            AutoEllipsis = true
        };
        _orderList.Dock = DockStyle.Fill; _orderList.ColumnCount = 1; _orderList.RowCount = 10; _orderList.Padding = Padding.Empty; _orderList.BackColor = Color.FromArgb(190, 202, 216);
        _orderList.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        for (var row = 0; row < 10; row++)
        {
            var n = 10 - row; _orderList.RowStyles.Add(new RowStyle(SizeType.Percent, 10));
            var item = new Label
            {
                Text = $"  {n:00}번 위치    -",
                Dock = DockStyle.Fill,
                BorderStyle = BorderStyle.FixedSingle,
                BackColor = row % 2 == 0 ? Color.White : Color.FromArgb(246, 249, 252),
                ForeColor = Color.FromArgb(36, 94, 160),
                Font = new Font("맑은 고딕", 8F, FontStyle.Regular),
                TextAlign = ContentAlignment.MiddleLeft,
                AutoEllipsis = true,
                Margin = Padding.Empty,
                Padding = new Padding(2, 0, 2, 0)
            };
            _orderList.Controls.Add(item, 0, row);
        }
        orderLayout.Controls.Add(legend, 0, 0); orderLayout.Controls.Add(_orderList, 0, 1); orderGroup.Controls.Add(orderLayout);
        root.Controls.Add(orderGroup, 1, 0); root.SetRowSpan(orderGroup, 2);
        return group;
    }

    private Control CreateFaultPanel()
    {
        var group = new GroupBox { Text = "고장 정보", Dock = DockStyle.Fill };
        UiTheme.ConfigureGrid(_faultGrid); _faultGrid.Dock = DockStyle.Fill; _faultGrid.ReadOnly = true;
        foreach (var h in new[] { "Fault", "고장 모듈 No", "고장 셀 No", "고장 셀 전압[V]", "고장 셀 온도[℃]" }) _faultGrid.Columns.Add(h, h);
        _faultGrid.Columns.Add(new DataGridViewButtonColumn { Name = "Delete", HeaderText = "삭제", Text = "삭제", UseColumnTextForButtonValue = true, FlatStyle = FlatStyle.Standard, Width = 80, AutoSizeMode = DataGridViewAutoSizeColumnMode.None });
        _faultGrid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill; _faultGrid.Columns[5].AutoSizeMode = DataGridViewAutoSizeColumnMode.None; _faultGrid.Columns[5].Width = 80;
        _faultGrid.CellContentClick += (_, e) => { if (e.RowIndex < 0 || e.ColumnIndex != 5 || _faultGrid.Rows[e.RowIndex].Tag is not string key) return; _dismissedFaults.Add(key); RenderFaults(_latestSnapshot?.Faults ?? []); };
        group.Controls.Add(_faultGrid); return group;
    }

    private static void AddPair(FlowLayoutPanel panel, string label, Control control)
    {
        panel.Controls.Add(new Label { Text = label, AutoSize = true, Margin = new Padding(5, 7, 3, 0) });
        control.Margin = new Padding(0, 3, 8, 0); panel.Controls.Add(control);
    }

    private static void AddLogo(FlowLayoutPanel panel, string fileName, int width, int height)
    {
        var path = Path.Combine(AppContext.BaseDirectory, "Assets", fileName);
        if (!File.Exists(path)) return;
        panel.Controls.Add(new PictureBox
        {
            Image = LoadLogoWithControlBackground(path),
            BackColor = SystemColors.Control,
            SizeMode = PictureBoxSizeMode.Zoom,
            Width = width,
            Height = height,
            Margin = new Padding(15, 0, 0, 0)
        });
    }

    private static Image LoadLogoWithControlBackground(string path)
    {
        using var source = new Bitmap(path);
        var logo = new Bitmap(source);
        var imageBackground = logo.GetPixel(0, 0).ToArgb();

        for (var y = 0; y < logo.Height; y++)
        for (var x = 0; x < logo.Width; x++)
            if (logo.GetPixel(x, y).ToArgb() == imageBackground)
                logo.SetPixel(x, y, SystemColors.Control);

        return logo;
    }

    private void ConfigureModuleGrid(DataGridView grid, int start)
    {
        UiTheme.ConfigureGrid(grid); grid.Dock = DockStyle.Fill; grid.ReadOnly = true; grid.RowTemplate.Height = 42;
        foreach (var h in new[] { "모듈", "모듈 전압", "셀 전압 Max/Min[V]", "셀 온도 Max/Min[℃]", "경보", "통신상태", "모듈(셀)" }) grid.Columns.Add(h, h);
        grid.Columns.Add(new DataGridViewButtonColumn { Name = "EPO", HeaderText = "EPO", FlatStyle = FlatStyle.Standard });
        grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        for (var n = start; n < start + 5; n++) grid.Rows.Add($"#{n:00}", "-", "- / -", "- / -", "-", "-", "상세정보", GetEpoButtonText(n));
        grid.CellDoubleClick += (_, e) => { if (e.RowIndex < 0 || e.ColumnIndex == 7) return; var module = _modules.FirstOrDefault(m => m.Number == start + e.RowIndex); if (module is not null) new ModuleDetailDialog(module).Show(this); };
        grid.CellClick += async (_, e) => { if (e.RowIndex >= 0 && e.ColumnIndex == 7) await ConfirmEpoAsync(start + e.RowIndex); };
    }

    private async Task ConfirmEpoAsync(int moduleNumber)
    {
        var module = _modules[moduleNumber - 1]; if (!module.Connected) { MessageBox.Show(this, "통신 가능한 모듈이 아닙니다.", "전원 차단", MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
        var result = MessageBox.Show(this, $"⚠ 축전지 모듈 #{moduleNumber:00} 전원을 강제로 차단합니다.\n시스템이 즉시 종료될 수 있습니다.\n정말 실행하시겠습니까?", "전원 차단 확인", MessageBoxButtons.OKCancel, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2);
        if (result != DialogResult.OK) return;
        try { await _service.SetEpoAsync(moduleNumber, true, _lifetime.Token); UpdateEpoCutoffTime(moduleNumber, true); MessageBox.Show(this, $"모듈 #{moduleNumber:00} 강제 차단 명령이 성공했습니다.", "전원 차단", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        catch (Exception ex) { MessageBox.Show(this, ex.Message, "전원 차단 실패", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }

    private void ResetModuleState()
    {
        _modules = Enumerable.Range(1, 10).Select(number => new ModuleState { Number = number }).ToList();
        foreach (var grid in _moduleGrids)
        {
            for (var row = 0; row < grid.RowCount; row++)
            {
                for (var column = 1; column <= 6; column++)
                {
                    grid[column, row].Value = "-";
                    grid[column, row].Style.BackColor = Color.White;
                    grid[column, row].Style.ForeColor = Color.Black;
                }
                var moduleNumber = grid == _moduleGrids[0] ? row + 1 : row + 6;
                grid[7, row].Value = GetEpoButtonText(moduleNumber);
            }
        }
        _dismissedFaults.Clear();
        _faultGrid.Rows.Clear();
        _updated.Text = "최종업데이트시간 : 초기화됨";
        UpdateOrderView();
    }

    private string GetEpoButtonText(int moduleNumber) => _profile.EpoCutoffTimes.TryGetValue(moduleNumber, out var cutoffTime) && !string.IsNullOrWhiteSpace(cutoffTime) ? $"차단\n({cutoffTime})" : "차단";

    private void UpdateEpoCutoffTime(int moduleNumber, bool cutoff)
    {
        if (cutoff) _profile.EpoCutoffTimes[moduleNumber] = DateTime.Now.ToString("MM.dd HH:mm");
        else _profile.EpoCutoffTimes.Remove(moduleNumber);
        _profileStore.Save(_profile);
        var grid = moduleNumber <= 5 ? _moduleGrids[0] : _moduleGrids[1];
        grid[7, (moduleNumber - 1) % 5].Value = GetEpoButtonText(moduleNumber);
    }

    private async Task ConfirmFullEpoAsync(bool cutoff)
    {
        if (_fullEpoOperationActive) return;
        if (_latestSnapshot?.Connection != ConnectionState.Connected) { MessageBox.Show(this, "먼저 장비에 접속해 주세요.", cutoff ? "전체차단" : "전체복구", MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
        var operation = cutoff ? "전체차단" : "전체복구"; var modules = _modules.Where(m => m.Connected && (!cutoff || m.Status is "충전중" or "방전중" or "Standby")).Select(m => m.Number).Order().ToArray();
        if (modules.Length == 0) { MessageBox.Show(this, $"{operation} 가능한 모듈이 없습니다.", operation, MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
        var warning = cutoff ? "모든 통신 가능 축전지 모듈의 전원을 차단합니다.\n시스템이 즉시 종료될 수 있습니다." : "인식된 모든 축전지 모듈에 복구 명령을 전송합니다.";
        if (MessageBox.Show(this, $"{warning}\n\n대상: {string.Join(", ", modules.Select(n => $"#{n:00}"))}\n정말 실행하시겠습니까?", operation + " 확인", MessageBoxButtons.OKCancel, cutoff ? MessageBoxIcon.Error : MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2) != DialogResult.OK) return;
        _fullEpoOperationActive = true; UpdateFullEpoButtonState();
        using var progress = new EpoProgressDialog(modules, operation); progress.Show(this); var failures = new List<int>();
        try
        {
            foreach (var module in modules)
            {
                progress.UpdateModule(module, "진행 중", null); try { await _service.SetEpoAsync(module, cutoff, _lifetime.Token); UpdateEpoCutoffTime(module, cutoff); progress.UpdateModule(module, "성공", null); }
                catch (Exception ex) { failures.Add(module); progress.UpdateModule(module, "실패", ex.Message); }
                await Task.Delay(100, _lifetime.Token);
            }
            progress.Complete();
            MessageBox.Show(this, failures.Count == 0 ? $"{operation}이 완료되었습니다." : $"실패 모듈: {string.Join(", ", failures.Select(n => $"#{n:00}"))}", operation, MessageBoxButtons.OK, failures.Count == 0 ? MessageBoxIcon.Information : MessageBoxIcon.Error);
        }
        finally { _fullEpoOperationActive = false; UpdateFullEpoButtonState(); }
    }

    private void ConfigureFullEpoButtons()
    {
        _fullEpoPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50)); _fullEpoPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        _fullCutoffButton.Dock = DockStyle.Fill; _fullCutoffButton.Margin = new Padding(1); _fullCutoffButton.Padding = Padding.Empty; _fullCutoffButton.Font = new Font("맑은 고딕", 8F, FontStyle.Bold); _fullCutoffButton.ToolTipText("전체 모듈 강제 차단 (SNMP SET)");
        _fullRestoreButton.Dock = DockStyle.Fill; _fullRestoreButton.Margin = new Padding(1); _fullRestoreButton.Padding = Padding.Empty; _fullRestoreButton.Font = new Font("맑은 고딕", 8F, FontStyle.Bold); _fullRestoreButton.ToolTipText("전체 모듈 차단 복구 (SNMP SET)");
        _fullCutoffButton.Click += async (_, _) => await ConfirmFullEpoAsync(true); _fullRestoreButton.Click += async (_, _) => await ConfirmFullEpoAsync(false);
        _fullEpoPanel.Controls.Add(_fullCutoffButton, 0, 0); _fullEpoPanel.Controls.Add(_fullRestoreButton, 1, 0); _summary.Controls.Add(_fullEpoPanel);
        _summary.Resize += (_, _) => PositionFullEpoPanel(); _summary.Scroll += (_, _) => PositionFullEpoPanel();
        _summary.ColumnWidthChanged += (_, _) => PositionFullEpoPanel(); _summary.RowHeightChanged += (_, _) => PositionFullEpoPanel();
        _summary.Layout += (_, _) => PositionFullEpoPanel(); UpdateFullEpoButtonState();
    }

    private void PositionFullEpoPanel()
    {
        if (_summary.RowCount <= 5 || _summary.ColumnCount <= 5) return;
        var bounds = _summary.GetCellDisplayRectangle(5, 5, true); bounds.Inflate(-2, -2); _fullEpoPanel.Bounds = bounds; _fullEpoPanel.Visible = bounds.Width > 4 && bounds.Height > 4; _fullEpoPanel.BringToFront();
    }

    private void UpdateFullEpoButtonState()
    {
        _fullCutoffButton.Enabled = !_fullEpoOperationActive;
        _fullRestoreButton.Enabled = !_fullEpoOperationActive;
    }

    private void PopulateStaticRows()
    {
        var labels = new[,] {
            { "설비번호", "운용 관리자", "제조사", "모델명", "상면", "" },
            { "-", "-", "-", "-", "-", "-" },
            { "Rack 전압[V]", "SOC 충전율[%]", "Max 전압[V]", "Min 전압[V]", "Avg 전압[V]", "" },
            { "-", "-", "-", "-", "-", "-" },
            { "Rack 전류[A]", "방전 횟수", "Max 온도[℃]", "Min 온도[℃]", "Avg 온도[℃]", "EPO(전체모듈)" },
            { "-", "-", "-", "-", "-", "차단 / 복구" },
            { "과전압 충전차단", "고온 충전차단", "과전류 충전차단", "차단기 OFF", "충전전류제한[C]", "SOC충전제한[%]" },
            { "-", "-", "-", "-", "-", "-" } };
        for (var r = 0; r < 8; r++) for (var c = 0; c < 6; c++) { _summary[c, r].Value = labels[r, c]; if (r % 2 == 0) _summary[c, r].Style.BackColor = UiTheme.Header; }
        ConfigureSummaryLimitButton(4);
        ConfigureSummaryLimitButton(5);
        _summary.Rows[5].Height = 36;
        _summary.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill; _summary.RowHeadersVisible = false; _summary.ColumnHeadersVisible = false;
        for (var column = 0; column < 4; column++) _summary.Columns[column].FillWeight = 92;
        _summary.Columns[4].FillWeight = 125; _summary.Columns[5].FillWeight = 145; _summary.Columns[5].MinimumWidth = 105;
        PositionFullEpoPanel();
    }

    private void ConfigureSummaryLimitButton(int column)
    {
        var button = new DataGridViewButtonCell
        {
            FlatStyle = FlatStyle.Standard,
            Value = "-",
            ToolTipText = column == 4 ? "충전전류 제한값 설정" : "SOC 충전 제한값 설정"
        };
        button.Style.Alignment = DataGridViewContentAlignment.MiddleCenter;
        button.Style.Font = new Font("맑은 고딕", 9F, FontStyle.Bold);
        button.Style.Padding = new Padding(3);
        _summary[column, 7] = button;
    }

    private async void ToggleConnectionAsync(object? sender, EventArgs e)
    {
        try
        {
            if (_connect.Text == "접속종료") { CloseConnectionProgress(); _connect.Enabled = false; await _service.DisconnectAsync(); _connect.Enabled = true; ShowAutoCloseMessage("접속 종료", "축전지 시스템 연결 종료."); return; }
            var isSlave = _mode.Equals("Slave", StringComparison.OrdinalIgnoreCase);
            if (!int.TryParse(_port.Text, out var snmpPort) || snmpPort is < 1 or > 65535 ||
                !int.TryParse(_trapPort.Text, out var trapPort) || (isSlave ? trapPort is < 0 or > 65535 : trapPort is < 1 or > 65535))
            {
                MessageBox.Show(this, isSlave
                    ? "SNMP Port는 1~65535, Slave TRAP Port는 0(자동 할당) 또는 1~65535 범위의 숫자로 입력하세요."
                    : "SNMP Port와 TRAP Port는 1~65535 범위의 숫자로 입력하세요.", "포트 입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Warning); return;
            }
            var options = new ConnectionOptions(_ip.Text.Trim(), snmpPort, _get.Text, _set.Text, _trap.Text, trapPort, _mode.Equals("Master", StringComparison.OrdinalIgnoreCase));
            ShowConnectionProgress($"1/3  SNMP 접속 시험 중...\r\n\r\n대상: {options.Address}:{options.Port}/UDP\r\n장비의 응답을 기다리고 있습니다."); _connect.Enabled = false; _connect.Text = "접속시험중";
            await _service.ConnectAsync(options, _lifetime.Token);
            UpdateConnectionProgress("2/3  SNMP 접속 성공\r\n\r\n3/3  축전지 시스템 정보를 수신 중입니다...\r\n초기 정보 수신이 끝나면 이 창은 자동으로 닫힙니다."); _connect.Enabled = true; _connect.Text = "접속종료";
            _profile.Address = options.Address; _profile.Port = options.Port; _profile.GetCommunity = options.GetCommunity; _profile.SetCommunity = options.SetCommunity;
            _profile.TrapCommunity = options.TrapCommunity;
            if (!isSlave) _profile.TrapPort = options.TrapPort;
            _profileStore.Save(_profile);
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested) { }
        catch (Exception ex) { CloseConnectionProgress(); _connect.Enabled = true; _connect.Text = "접속시작"; ShowSnmpConnectionFailure(ex.Message); }
    }

    private void OnSnapshotChanged(object? sender, MonitorSnapshot snapshot)
    {
        if (InvokeRequired) { BeginInvoke(() => OnSnapshotChanged(sender, snapshot)); return; }
        _connect.Text = snapshot.Connection switch { ConnectionState.Connected => "접속종료", ConnectionState.Connecting => "접속시험중", _ => "접속시작" };
        _connectionDot.ForeColor = snapshot.Connection == ConnectionState.Connected ? Color.FromArgb(46, 195, 112) : Color.Gray;
        _updated.Text = snapshot.UpdatedAt is { } t ? $"최종업데이트시간 : {t:yyyy-MM-dd HH:mm:ss}" : "최종업데이트시간 : 대기중";
        _timeout.Text = $"Timeout : {snapshot.ConsecutiveFailures} / {snapshot.TotalFailures}";
        if (snapshot.Connection == ConnectionState.Connected && snapshot.RawValues.Count > 0) CloseConnectionProgress();
        _timeout.ToolTipText(snapshot.LastError);
        if (snapshot.ConsecutiveFailures == 0) { _timeoutWarningShown = false; _timeoutDisconnectedShown = false; }
        if (snapshot.ConsecutiveFailures >= 5 && !_timeoutWarningShown) { _timeoutWarningShown = true; MessageBox.Show(this, $"설치 장소: {_profile.Site}\n축전지명: {_profile.SystemName}\nIP: {_profile.Address}\n\n접속 중 Timeout이 연속 5회 발생했습니다.", "Timeout 발생", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        if (snapshot.ConsecutiveFailures >= 30 && !_timeoutDisconnectedShown) { _timeoutDisconnectedShown = true; MessageBox.Show(this, "지속적인 Timeout으로 접속을 종료합니다.", "연결 종료", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        UpdateModuleViews(snapshot);
        UpdateFullEpoButtonState();
        UpdateActiveAlarmButton(snapshot);
        UpdateAlarmSound(snapshot);
        if (_mode.Equals("Slave", StringComparison.OrdinalIgnoreCase))
        {
            if (snapshot.Connection == ConnectionState.Connected && !_slaveStarted)
            {
                try { var port = _slaveCoordinator.StartSlave(_profile.Address, _profile.LocalTrapPort, _profile.FilePath, _profile.SystemName, _lifetime.Token); _profile.LocalTrapPort = port; _profileStore.Save(_profile); _trapPort.Text = port.ToString(); _slaveStarted = true; }
                catch (Exception ex) { ShowTrapListenerFailure(ex.Message); }
            }
            else if (snapshot.Connection == ConnectionState.Disconnected && _slaveStarted) { _slaveCoordinator.Stop(); _slaveStarted = false; }
        }
    }

    private void ShowConnectionProgress(string message)
    {
        CloseConnectionProgress();
        var dialog = new Form { Text = "축전지 시스템 접속 진행", StartPosition = FormStartPosition.CenterParent, FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false, ShowInTaskbar = false, ClientSize = new Size(480, 155), Font = new Font("맑은 고딕", 9F) };
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, Padding = new Padding(18) }; layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 24));
        var label = new Label { Text = message, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft, AutoEllipsis = true }; var progress = new ProgressBar { Dock = DockStyle.Fill, Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 35 };
        layout.Controls.Add(label, 0, 0); layout.Controls.Add(progress, 0, 1); dialog.Controls.Add(layout); dialog.FormClosed += (_, _) => { if (ReferenceEquals(_connectionProgress, dialog)) { _connectionProgress = null; _connectionProgressText = null; } };
        _connectionProgress = dialog; _connectionProgressText = label; dialog.Show(this); dialog.BringToFront();
    }

    private void UpdateConnectionProgress(string message) { if (_connectionProgressText is not null && !_connectionProgressText.IsDisposed) _connectionProgressText.Text = message; }
    private void CloseConnectionProgress() { var dialog = _connectionProgress; _connectionProgress = null; _connectionProgressText = null; if (dialog is not null && !dialog.IsDisposed) dialog.Close(); }

    private void ShowSnmpConnectionFailure(string error)
    {
        var message = $"축전지 시스템의 SNMP 응답을 받지 못했습니다.\r\n\r\n대상: {_ip.Text.Trim()}:{_port.Text.Trim()}/UDP\r\n오류: {(!string.IsNullOrWhiteSpace(error) ? error : "응답 시간 초과 또는 원인 정보 없음")}\r\n\r\n확인 및 조치 방법\r\n1. 대상 장비의 전원과 네트워크 연결을 확인합니다.\r\n2. IP 주소와 SNMP Port가 장비 설정과 같은지 확인합니다.\r\n3. 장비에서 SNMP 서비스와 SNMP v2c가 활성화되어 있는지 확인합니다.\r\n4. GET Community 문자열과 장비의 접근 허용 IP(ACL)를 확인합니다.\r\n5. PC·네트워크 방화벽에서 대상 UDP 포트 통신을 허용합니다.\r\n\r\n※ 이 Port는 로컬 수신 포트가 아니라 대상 장비의 SNMP GET/SET 서비스 포트입니다.";
        MessageBox.Show(this, message, "SNMP 접속 실패 - 확인 및 조치 안내", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private void ShowTrapListenerFailure(string error)
    {
        var normalized = (error ?? "").ToLowerInvariant(); var reason = normalized.Contains("10048") || normalized.Contains("address already in use") ? "선택한 UDP 포트를 다른 프로그램 또는 서비스가 이미 사용 중입니다." : normalized.Contains("10013") || normalized.Contains("permission") || normalized.Contains("access") ? "UDP 포트를 열 권한이 없거나 보안 정책에서 사용을 차단했습니다." : normalized.Contains("10049") || normalized.Contains("cannot assign requested address") ? "현재 PC에서 사용할 수 없는 수신 주소로 바인딩을 시도했습니다." : "운영체제에서 UDP 수신 포트를 열지 못했습니다.";
        var message = $"SNMP 접속은 정상이나 Trap 이벤트 수신 포트를 열지 못했습니다.\r\n\r\n수신 포트: 0.0.0.0:{_trapPort.Text.Trim()}/UDP\r\n원인: {reason}\r\n상세 오류: {(!string.IsNullOrWhiteSpace(error) ? error : "원인 정보 없음")}\r\n\r\n영향\r\n주기적인 SNMP 상태 조회는 계속되지만 실시간 알람/복구 Trap은 수신할 수 없습니다.\r\n\r\n확인 및 조치 방법\r\n1. Windows SNMP Trap 서비스 또는 동일 포트를 쓰는 프로그램을 종료합니다.\r\n2. 다른 UDP Trap Port를 사용한다면 장비의 Trap 목적지 포트도 동일하게 변경합니다.\r\n3. Windows 방화벽에서 해당 UDP 포트의 인바운드 수신을 허용합니다.\r\n4. 권한 오류가 계속되면 관리자 권한 및 보안 정책을 확인합니다.\r\n5. 조치 후 프로그램 접속을 종료하고 다시 시작합니다.\r\n\r\nHOST의 TRAP 포트 점유 해제 방법\r\n관리자 권한으로 PowerShell을 실행한 후 아래 명령을 입력합니다.\r\n\r\nSet-Service SNMPTRAP -StartupType Disabled\r\nStop-Service SNMPTRAP\r\nStop-Process -Name \"MgWTrap3\" -Force\r\n\r\n※ 위 명령은 Windows SNMP Trap 서비스를 중지·비활성화하고 MgWTrap3 프로세스를 강제 종료합니다.";
        using var dialog = new Form
        {
            Text = "Trap 수신 포트 실패 - 제한 기능 및 조치 안내",
            StartPosition = FormStartPosition.CenterParent,
            FormBorderStyle = FormBorderStyle.Sizable,
            MinimizeBox = false,
            ShowInTaskbar = false,
            ClientSize = new Size(720, 610),
            MinimumSize = new Size(620, 480),
            Font = new Font("맑은 고딕", 9F)
        };
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, Padding = new Padding(12) };
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        var guide = new TextBox
        {
            Text = message,
            Dock = DockStyle.Fill,
            Multiline = true,
            ReadOnly = true,
            ScrollBars = ScrollBars.Vertical,
            BackColor = Color.White,
            WordWrap = false
        };
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(0, 6, 0, 0) };
        var ok = UiTheme.Button("확인"); ok.Width = 85; ok.DialogResult = DialogResult.OK; buttons.Controls.Add(ok);
        layout.Controls.Add(guide, 0, 0); layout.Controls.Add(buttons, 0, 1); dialog.Controls.Add(layout);
        dialog.AcceptButton = ok;
        dialog.Shown += (_, _) => { guide.SelectionLength = 0; guide.Select(0, 0); };
        dialog.ShowDialog(this);
    }

    private void ShowAutoCloseMessage(string title, string message, int durationMilliseconds = 1500)
    {
        var dialog = new Form { Text = title, StartPosition = FormStartPosition.CenterParent, FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false, ShowInTaskbar = false, ClientSize = new Size(350, 105), Font = new Font("맑은 고딕", 9F) };
        dialog.Controls.Add(new Label { Text = message, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter });
        var timer = new System.Windows.Forms.Timer { Interval = durationMilliseconds }; timer.Tick += (_, _) => { timer.Stop(); timer.Dispose(); if (!dialog.IsDisposed) dialog.Close(); }; dialog.FormClosed += (_, _) => { timer.Stop(); timer.Dispose(); };
        dialog.Show(this); dialog.BringToFront(); timer.Start();
    }

    private void UpdateModuleViews(MonitorSnapshot snapshot)
    {
        _latestSnapshot = snapshot;
        _modules = snapshot.Modules;
        foreach (var module in snapshot.Modules)
        {
            var grid = module.Number <= 5 ? _moduleGrids[0] : _moduleGrids[1]; var row = (module.Number - 1) % 5;
            var cells = module.CellVoltages.Where(v => v.HasValue).Select(v => v!.Value).ToArray(); var temps = module.CellTemperatures.Where(v => v.HasValue).Select(v => v!.Value).ToArray();
            grid[1, row].Value = Format(module.Voltage, "0.0"); grid[2, row].Value = cells.Length == 0 ? "- / -" : $"{cells.Max():0.00} / {cells.Min():0.00}";
            grid[3, row].Value = temps.Length == 0 ? "- / -" : $"{temps.Max():0.0} / {temps.Min():0.0}"; grid[4, row].Value = module.Alarm == AlarmLevel.Normal ? "정상" : "이상"; grid[4, row].Style.BackColor = UiTheme.ForAlarm(module.Alarm);
            grid[5, row].Value = module.Status; grid[5, row].Style.BackColor = module.Connected ? UiTheme.Mint : UiTheme.Disabled; grid[6, row].Value = module.Connected ? "상세정보" : "-";
        }
        var summary = SystemSummaryService.Create(snapshot);
        foreach (var item in summary.Values) SetSummary(item.Key, item.Value);
        _summaryGroup.Text = summary.Title;
        static string Format(double? value, string format) => value?.ToString(format) ?? "-";
        RenderFaults(snapshot.Faults);
        UpdateOrderView();
    }

    private void RenderFaults(IReadOnlyList<FaultEntry> faults)
    {
        var activeKeys = faults.Select(FaultKey).ToHashSet(StringComparer.OrdinalIgnoreCase); _dismissedFaults.RemoveWhere(key => !activeKeys.Contains(key));
        _faultGrid.Rows.Clear(); var faultNo = 1;
        foreach (var fault in faults.Where(fault => !_dismissedFaults.Contains(FaultKey(fault))))
        {
            var hardwareFault = fault.CellNo == 0 && (fault.Fault.Contains("Board hardware fault", StringComparison.OrdinalIgnoreCase) || fault.Fault.Contains("BMS hardware fault", StringComparison.OrdinalIgnoreCase));
            var rowIndex = _faultGrid.Rows.Add($"#{faultNo++:00}", fault.ModuleNo == 0 ? "SYSTEM" : fault.ModuleNo, hardwareFault ? "(BMS hardware fault)" : fault.CellNo == 0 ? "-" : fault.CellNo, hardwareFault ? "-" : fault.Voltage?.ToString("0.00") ?? "-", hardwareFault ? "-" : fault.Temperature?.ToString("0.0") ?? "-");
            var row = _faultGrid.Rows[rowIndex]; row.Tag = FaultKey(fault); row.DefaultCellStyle.BackColor = Color.FromArgb(242, 95, 92); row.DefaultCellStyle.ForeColor = Color.White;
            if (hardwareFault) for (var column = 2; column <= 4; column++) { row.Cells[column].Style.BackColor = Color.FromArgb(85, 85, 85); row.Cells[column].Style.ForeColor = Color.White; }
            row.Cells[5].Style.BackColor = SystemColors.Control; row.Cells[5].Style.ForeColor = Color.Black;
        }
    }

    private static string FaultKey(FaultEntry fault) => $"{fault.ModuleNo}\u001f{fault.CellNo}\u001f{fault.Fault}";

    private void SetSummary(string label, string value) { var position = SummaryPositions[label]; var cell = _summary[position.Column, position.Row]; cell.Value = value; cell.Style.BackColor = value switch { "-" => Color.White, "비정상" => UiTheme.Critical, _ => UiTheme.Mint }; cell.Style.ForeColor = value == "비정상" ? Color.White : Color.Black; }
    private void UpdateActiveAlarmButton(MonitorSnapshot snapshot)
    {
        var count = snapshot.ActiveAlarms.Count; var connected = snapshot.Connection == ConnectionState.Connected; _activeAlarmButton.Text = count > 0 ? $"발생된 알람 보기 ({count})" : "발생된 알람 보기"; _activeAlarmButton.Enabled = connected;
        if (connected && count > 0) { if (!_alarmBlinkTimer.Enabled) { _alarmBlinkOn = true; ApplyActiveAlarmButtonStyle(true); _alarmBlinkTimer.Start(); } }
        else { _alarmBlinkTimer.Stop(); _alarmBlinkOn = false; ApplyActiveAlarmButtonStyle(false); }
    }
    private void ApplyActiveAlarmButtonStyle(bool alarmOn)
    {
        var background = alarmOn ? Color.FromArgb(211, 47, 47) : Color.FromArgb(241, 243, 245); _activeAlarmButton.BackColor = background; _activeAlarmButton.ForeColor = alarmOn ? Color.White : Color.FromArgb(44, 62, 80); _activeAlarmButton.FlatAppearance.BorderColor = alarmOn ? background : Color.FromArgb(158, 158, 158); _activeAlarmButton.FlatAppearance.BorderSize = 1;
    }
    private string SoundText() => _profile.AlarmVolume switch { 0 => "🔇", 1 => "🔈", 2 => "🔉", _ => "🔊" };
    private void UpdateAlarmSound(MonitorSnapshot? snapshot)
    {
        var shouldPlay = _profile.AlarmVolume > 0 && snapshot?.ActiveAlarms.Any(a => _profile.AlarmLevels.GetValueOrDefault(a.Level switch { AlarmLevel.Critical => 1, AlarmLevel.Major => 2, AlarmLevel.Minor => 3, AlarmLevel.Warning => 4, _ => 255 })) == true;
        try { if (shouldPlay && !_alarmPlaying) { _alarmPlayer?.PlayLooping(); _alarmPlaying = true; } else if (!shouldPlay && _alarmPlaying) { _alarmPlayer?.Stop(); _alarmPlaying = false; } } catch (InvalidOperationException) { _alarmPlaying = false; }
    }
    private void UpdateOrderView()
    {
        if (_orderList.Controls.Count == 0) return;
        for (var index = 0; index < 10; index++)
        {
            var position = 10 - index; var moduleNo = _profile.ModuleOrder.ElementAtOrDefault(position - 1); var module = _modules.FirstOrDefault(m => m.Number == moduleNo);
            var liveBarcode = module?.Barcode is { Length: > 1 } code && code != "-" ? code : ""; var savedBarcode = _profile.ModuleBarcodes.GetValueOrDefault(moduleNo, ""); var barcode = liveBarcode.Length > 0 ? liveBarcode : savedBarcode.Length > 0 ? savedBarcode : "-";
            var item = (Label)_orderList.Controls[index]; item.Text = moduleNo is >= 1 and <= 10 ? $"  {position:00}번 위치    {barcode}    [모듈 {moduleNo:00}]" : $"  {position:00}번 위치    -";
            var isDisconnected = module?.Status.Equals("Disconnect", StringComparison.OrdinalIgnoreCase) == true; var hasAlarm = module is not null && module.Alarm != AlarmLevel.Normal; var barcodeMismatch = liveBarcode.Length > 0 && savedBarcode.Length > 0 && !liveBarcode.Equals(savedBarcode, StringComparison.Ordinal);
            item.BackColor = isDisconnected ? Color.FromArgb(173, 181, 189) : hasAlarm ? Color.FromArgb(220, 53, 69) : barcodeMismatch && _moduleOrderBlinkOn ? Color.FromArgb(255, 235, 59) : index % 2 == 0 ? Color.White : Color.FromArgb(246, 249, 252);
            item.ForeColor = isDisconnected || hasAlarm ? Color.White : barcodeMismatch && _moduleOrderBlinkOn ? Color.FromArgb(55, 65, 81) : Color.FromArgb(36, 94, 160);
        }
    }

    private async Task OpenChargeLimitAsync()
    {
        if (_latestSnapshot?.Connection != ConnectionState.Connected) { MessageBox.Show(this, "먼저 장비에 접속해 주세요."); return; }
        try { var current = await _service.GetChargeLimitAsync(_lifetime.Token); using var dialog = new ChargeLimitDialog(current); if (dialog.ShowDialog(this) != DialogResult.OK) return; await _service.SetChargeLimitAsync(dialog.SnmpValue, _lifetime.Token); MessageBox.Show(this, $"충전전류 제한이 {dialog.SnmpValue / 100d:0.00}C로 설정되었습니다.", "설정 성공", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        catch (Exception ex) { MessageBox.Show(this, ex.Message, "충전전류 제한 오류", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }
    private async Task OpenSocLimitAsync()
    {
        if (_latestSnapshot?.Connection != ConnectionState.Connected) { MessageBox.Show(this, "먼저 장비에 접속해 주세요."); return; }
        try { var current = await _service.GetSocChargeLimitAsync(_lifetime.Token); using var dialog = new SocLimitDialog(current.Enabled, current.Value); if (dialog.ShowDialog(this) != DialogResult.OK) return; await _service.SetSocChargeLimitAsync(dialog.EnabledValue, dialog.LimitValue, _lifetime.Token); MessageBox.Show(this, dialog.EnabledValue == 1 ? "SOC 충전 제한을 사용하지 않도록 설정했습니다." : $"SOC 충전 제한이 {dialog.LimitValue}%로 설정되었습니다.", "설정 성공", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        catch (Exception ex) { MessageBox.Show(this, ex.Message, "SOC 충전 제한 오류", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }
    private async Task RequestTrapRetransmitAsync(Button button)
    {
        if (_latestSnapshot?.Connection != ConnectionState.Connected) { MessageBox.Show(this, "먼저 장비에 접속해 주세요."); return; } button.Enabled = false;
        try { await _service.RequestTrapRetransmissionAsync(_lifetime.Token); MessageBox.Show(this, "장비에 누락 Trap 재전송을 요청했습니다.", "재전송요청", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        catch (Exception ex) { MessageBox.Show(this, ex.Message, "재전송요청 실패", MessageBoxButtons.OK, MessageBoxIcon.Error); } finally { if (!button.IsDisposed) button.Enabled = true; }
    }

    private void OnTrapReceived(object? sender, TrapEntry entry)
    {
        if (InvokeRequired) { BeginInvoke(() => OnTrapReceived(sender, entry)); return; }
        try { _trapLogger.Append(entry); }
        catch (Exception ex) { Debug.WriteLine($"Trap log write failed: {ex.Message}"); }
        _trapGrid.Rows.Insert(0, entry.Time.ToString("yyyy-MM-dd HH:mm:ss"), entry.Oid, entry.OrdinalNumber, entry.Alarm, entry.Level, entry.EquipmentId, entry.EquipmentName, entry.FatherEquipment);
        _trapGrid.Rows[0].DefaultCellStyle.BackColor = entry.IsResume ? UiTheme.Mint : Color.FromArgb(255, 107, 107);
        _trapGrid.Rows[0].DefaultCellStyle.ForeColor = entry.IsResume ? Color.Black : Color.White;
        if (_trapGrid.Rows.Count > 1000) _trapGrid.Rows.RemoveAt(_trapGrid.Rows.Count - 1);
    }

    private void UpdateResourceLabel()
    {
        using var process = Process.GetCurrentProcess();
        var sampledAt = DateTime.UtcNow; var totalCpu = process.TotalProcessorTime; var cpuUsage = 0d;
        if (_lastCpuSampleAt != default)
        {
            var elapsedMs = (sampledAt - _lastCpuSampleAt).TotalMilliseconds; var cpuMs = (totalCpu - _lastCpuTime).TotalMilliseconds;
            if (elapsedMs > 0) cpuUsage = Math.Clamp(cpuMs / (elapsedMs * Environment.ProcessorCount) * 100d, 0d, 100d);
        }
        _lastCpuSampleAt = sampledAt; _lastCpuTime = totalCpu;
        var memory = process.WorkingSet64 / 1024d / 1024d;
        _resource.Text = $" CPU[{cpuUsage,6:0.00}%] MEM[ {memory,6:0.0}MB] Thread[ {process.Threads.Count,2}] TRAP[ 0/s] QUEUE[ 0/0]";
    }

    private async void OnFormClosingAsync(object? sender, FormClosingEventArgs e)
    {
        RemoveOwnedMasterMarker();
        _lifetime.Cancel(); _resourceTimer.Stop(); _alarmBlinkTimer.Stop();
        await _service.DisconnectAsync(); await _service.DisposeAsync(); _lifetime.Dispose();
        await _operationRecorder.DisposeAsync();
        await _slaveCoordinator.DisposeAsync();
        _alarmPlayer?.Stop(); _alarmPlayer?.Dispose(); _alarmBlinkTimer.Dispose();
    }

    private void RemoveOwnedMasterMarker()
    {
        if (!_ownsMasterMarker) return;
        try
        {
            var markedProfile = File.Exists(_masterMarkerPath) ? File.ReadAllText(_masterMarkerPath).Trim() : "";
            if (markedProfile.Length > 0 && Path.GetFullPath(markedProfile).Equals(Path.GetFullPath(_profile.FilePath), StringComparison.OrdinalIgnoreCase)) File.Delete(_masterMarkerPath);
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        finally { _ownsMasterMarker = false; }
    }
}

internal static class ToolTipExtensions
{
    private static readonly ToolTip ToolTip = new();
    public static void ToolTipText(this Control control, string? text) => ToolTip.SetToolTip(control, text ?? "");
}
