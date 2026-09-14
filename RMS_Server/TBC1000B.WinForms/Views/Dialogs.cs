using TBC1000B.WinForms.Models;
using TBC1000B.WinForms.Services;

namespace TBC1000B.WinForms.Views;

public sealed class OperationRecordDialog : Form
{
    private readonly OperationRecordService _recorder;
    private readonly Func<MonitorSnapshot?> _snapshotProvider;
    private readonly Dictionary<string, CheckBox> _fieldBoxes = [];
    private readonly Label _status = new();
    private readonly System.Windows.Forms.Timer _statusTimer = new() { Interval = 1000 };
    public OperationRecordDialog(OperationRecordService recorder, Func<MonitorSnapshot?> snapshotProvider)
    {
        _recorder = recorder; _snapshotProvider = snapshotProvider;
        Text = "운전 데이터 기록 설정"; ClientSize = new Size(450, 614); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; StartPosition = FormStartPosition.CenterParent;
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(18), RowCount = 8 };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 65)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 195)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 96)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 64)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 34)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 44)); Controls.Add(root);
        root.Controls.Add(new Label { Text = "운전 데이터 기록 주기", Font = new Font("맑은 고딕", 11F, FontStyle.Bold), Dock = DockStyle.Fill });
        var settings = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 2, GrowStyle = TableLayoutPanelGrowStyle.FixedSize };
        settings.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 95));
        settings.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        settings.RowStyles.Add(new RowStyle(SizeType.Percent, 50));
        settings.RowStyles.Add(new RowStyle(SizeType.Percent, 50));
        settings.Controls.Add(new Label { Text = "기록 간격", Dock = DockStyle.Fill, AutoSize = false, TextAlign = ContentAlignment.MiddleLeft }, 0, 0);
        var intervalInput = new ComboBox { Dock = DockStyle.Fill, Items = { "1분", "5분", "10분", "30분", "60분" }, Text = "5분" };
        settings.Controls.Add(intervalInput, 1, 0);
        settings.Controls.Add(new Label { Text = "기록 기간", Dock = DockStyle.Fill, AutoSize = false, TextAlign = ContentAlignment.MiddleLeft }, 0, 1);
        var durationInput = new DayNumericUpDown { Dock = DockStyle.Fill, Minimum = 1, Maximum = 3650, Value = 30 };
        settings.Controls.Add(durationInput, 1, 1);
        root.Controls.Add(settings);
        var title = new FlowLayoutPanel { Dock = DockStyle.Fill }; title.Controls.Add(new Label { Text = "Excel 기록 항목", Font = new Font("맑은 고딕", 10F, FontStyle.Bold), Width = 185 });
        var all = UiTheme.Button("전체선택"); all.Width = 90; var clear = UiTheme.Button("전체해제"); clear.Width = 90; title.Controls.Add(all); title.Controls.Add(clear); root.Controls.Add(title);
        var checks = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 7 };
        var boxes = OperationRecordService.FieldSpecs.Select(s => { var box = new CheckBox { Text = s.Label, Checked = true, AutoSize = true }; _fieldBoxes[s.Key] = box; return box; }).ToArray();
        for (var i = 0; i < boxes.Length; i++) checks.Controls.Add(boxes[i], i % 2, i / 2); all.Click += (_, _) => Array.ForEach(boxes, b => b.Checked = true); clear.Click += (_, _) => Array.ForEach(boxes, b => b.Checked = false);
        root.Controls.Add(checks);
        var recordPath = Path.Combine(Environment.CurrentDirectory, "Operation data record");
        root.Controls.Add(new Label { Text = $"저장 위치\n{WrapPath(recordPath)}", Dock = DockStyle.Fill, BackColor = Color.FromArgb(245, 249, 253), ForeColor = Color.SlateGray, Padding = new Padding(8, 6, 8, 6), AutoSize = false, TextAlign = ContentAlignment.MiddleLeft });
        root.Controls.Add(new Label { Text = "예상 기록량: 86,400행 / 48열\n권장 최소 여유 공간: 138 MB", Dock = DockStyle.Fill, BackColor = Color.FromArgb(241, 247, 255), ForeColor = Color.RoyalBlue, BorderStyle = BorderStyle.FixedSingle, Padding = new Padding(8, 7, 8, 7), TextAlign = ContentAlignment.MiddleLeft });
        _status.Text = "기록이 중지되어 있습니다."; _status.ForeColor = Color.Gray; _status.Dock = DockStyle.Fill; _status.TextAlign = ContentAlignment.MiddleLeft; root.Controls.Add(_status);
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(0, 3, 0, 4), Margin = Padding.Empty, WrapContents = false }; var start = UiTheme.Button("기록시작", Color.FromArgb(16, 164, 83)); start.Width = 90; start.Height = 30; var stop = UiTheme.Button("기록중지"); stop.Width = 90; stop.Height = 30; stop.Enabled = false; var close = UiTheme.Button("닫기"); close.Width = 90; close.Height = 30; close.Margin = new Padding(120, 3, 0, 3); close.Click += (_, _) => Close(); buttons.Controls.AddRange([start, stop, close]); root.Controls.Add(buttons);
        start.Click += (_, _) =>
        {
            if (_snapshotProvider()?.Connection != ConnectionState.Connected) { MessageBox.Show(this, "먼저 축전지 시스템에 접속해 주세요.", "기록 시작 불가", MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
            var fields = _fieldBoxes.Where(x => x.Value.Checked).Select(x => x.Key).ToHashSet(StringComparer.Ordinal); if (fields.Count == 0) { MessageBox.Show(this, "기록 항목을 하나 이상 선택하세요."); return; }
            var intervalText = ((ComboBox)settings.GetControlFromPosition(1, 0)!).Text.Replace("분", ""); var interval = int.TryParse(intervalText, out var parsed) ? parsed : 5; var duration = (int)durationInput.Value;
            _recorder.Start(new OperationRecordOptions(interval, duration, fields), _snapshotProvider); UpdateState(start, stop, boxes);
        };
        stop.Click += (_, _) => { _recorder.Stop(); UpdateState(start, stop, boxes); };
        _recorder.FileSaved += OnSaved; _recorder.Error += OnError; _statusTimer.Tick += (_, _) => UpdateStatus(); _statusTimer.Start(); UpdateState(start, stop, boxes);
        FormClosed += (_, _) => { _statusTimer.Stop(); _recorder.FileSaved -= OnSaved; _recorder.Error -= OnError; };
    }
    private void UpdateState(Button start, Button stop, IEnumerable<CheckBox> boxes) { start.Enabled = !_recorder.IsRecording; stop.Enabled = _recorder.IsRecording; foreach (var box in boxes) box.Enabled = !_recorder.IsRecording; UpdateStatus(); }
    private static string WrapPath(string path, int maximumLineLength = 42)
    {
        var parts = path.Split(Path.DirectorySeparatorChar); var lines = new List<string>(); var current = "";
        foreach (var part in parts)
        {
            var candidate = current.Length == 0 ? part : $"{current}/{part}";
            if (current.Length > 0 && candidate.Length > maximumLineLength) { lines.Add(current + "/"); current = part; }
            else current = candidate;
        }
        if (current.Length > 0) lines.Add(current); return string.Join(Environment.NewLine, lines);
    }
    private void UpdateStatus() { _status.Text = _recorder.IsRecording ? $"● 기록 중 · 종료 {_recorder.EndsAt:MM.dd HH:mm}" : "기록이 중지되어 있습니다."; _status.ForeColor = _recorder.IsRecording ? Color.Green : Color.Gray; }
    private void OnSaved(object? sender, string path) { if (!IsDisposed) BeginInvoke(() => { _status.Text = $"● {DateTime.Now:HH:mm:ss} 저장 완료"; _status.Tag = path; }); }
    private void OnError(object? sender, string message) { if (!IsDisposed) BeginInvoke(() => { _status.Text = message; _status.ForeColor = Color.Red; }); }
}

public sealed class ModuleOrderDialog : Form
{
    private readonly ComboBox[] _combos = new ComboBox[10]; private readonly Profile _profile; private readonly ProfileStore _store; private readonly IReadOnlyList<ModuleState> _modules;
    public ModuleOrderDialog(Profile profile, ProfileStore store, IReadOnlyList<ModuleState> modules)
    {
        _profile = profile; _store = store; _modules = modules;
        Text = "모듈 설치 순서 설정"; ClientSize = new Size(700, 560); MinimumSize = new Size(650, 520); StartPosition = FormStartPosition.CenterParent;
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(12), ColumnCount = 2, RowCount = 2 };
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 185)); root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); root.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 36)); Controls.Add(root);
        var asset = Path.Combine(AppContext.BaseDirectory, "Assets", "install_battery.png"); var picture = new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom, Margin = new Padding(0, 0, 8, 0) }; if (File.Exists(asset)) picture.Image = Image.FromFile(asset); root.Controls.Add(picture, 0, 0);
        var list = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 10, ColumnCount = 2 }; list.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 85)); list.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); for (var row = 0; row < 10; row++) list.RowStyles.Add(new RowStyle(SizeType.Percent, 10));
        for (var pos = 10; pos >= 1; pos--)
        {
            list.Controls.Add(new Label { Text = $"{pos:00}번 위치", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill, Margin = new Padding(3) });
            var combo = new ComboBox { Dock = DockStyle.Fill, DropDownStyle = ComboBoxStyle.DropDownList, Margin = new Padding(3, 5, 3, 3) }; combo.Items.Add("-");
            for (var n = 1; n <= 10; n++) { var module = modules.FirstOrDefault(item => item.Number == n); var deviceBarcode = module?.Barcode is { Length: > 1 } value && value != "-" ? value : ""; var savedBarcode = profile.ModuleBarcodes.GetValueOrDefault(n, ""); var barcode = deviceBarcode.Length > 0 ? deviceBarcode : savedBarcode; combo.Items.Add($"모듈{n:00}-{(barcode.Length > 0 ? barcode : "-")}"); }
            var current = profile.ModuleOrder.ElementAtOrDefault(pos - 1); combo.SelectedIndex = current is >= 1 and <= 10 ? current : 0; _combos[pos - 1] = combo; list.Controls.Add(combo);
        }
        root.Controls.Add(list, 1, 0);
        var reset = UiTheme.Button("초기화"); reset.Dock = DockStyle.Fill; reset.Click += (_, _) => Array.ForEach(_combos, c => c.SelectedIndex = 0); var save = UiTheme.Button("저장"); save.Dock = DockStyle.Fill; save.Click += (_, _) => SaveOrder(); root.Controls.Add(reset, 0, 1); root.Controls.Add(save, 1, 1);
    }
    private void SaveOrder() { var selected = _combos.Select(c => c.SelectedIndex).Where(n => n > 0).ToArray(); if (selected.Length != selected.Distinct().Count()) { MessageBox.Show(this, "동일한 모듈을 여러 위치에 배치할 수 없습니다.", "설치 순서 오류", MessageBoxButtons.OK, MessageBoxIcon.Warning); return; } _profile.ModuleOrder = _combos.Select(c => c.SelectedIndex).ToArray(); foreach (var module in _modules.Where(module => module.Barcode is { Length: > 1 } && module.Barcode != "-")) _profile.ModuleBarcodes[module.Number] = module.Barcode; _store.Save(_profile); DialogResult = DialogResult.OK; Close(); }
}

public sealed class AllModulesDialog : Form
{
    private readonly System.Windows.Forms.Timer _refreshTimer = new() { Interval = 3000 };
    public AllModulesDialog(Func<IReadOnlyList<ModuleState>> getModules)
    {
        Text = "전체 모듈 상세정보"; WindowState = FormWindowState.Maximized; MinimumSize = new Size(1000, 520);
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(10), RowCount = 4 }; root.RowStyles.Add(new RowStyle(SizeType.Absolute, 28)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 30)); root.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 38)); Controls.Add(root);
        var heading = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2 }; heading.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50)); heading.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        heading.Controls.Add(new Label { Text = "전체 모듈 상세정보", Dock = DockStyle.Fill, Font = new Font("맑은 고딕", 11F, FontStyle.Bold), TextAlign = ContentAlignment.MiddleLeft });
        var updated = new Label { Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleRight };
        heading.Controls.Add(updated); root.Controls.Add(heading);
        root.Controls.Add(CreateCellLegend());
        var grid = new DataGridView { Dock = DockStyle.Fill, ReadOnly = true }; UiTheme.ConfigureGrid(grid);
        var headers = new List<string> { "모듈", "SW버전", "Equip ID", "모델", "바코드", "전압[V]", "전류[A]", "상태", "SOC[%]", "SOH[%]" }; headers.AddRange(Enumerable.Range(1, 15).Select(n => $"셀{n} 전압[V]")); headers.AddRange(Enumerable.Range(1, 15).Select(n => $"셀{n} 온도[℃]"));
        foreach (var h in headers) grid.Columns.Add(h, h);
        grid.ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.DisableResizing; grid.ColumnHeadersHeight = 38;
        grid.ColumnHeadersDefaultCellStyle.WrapMode = DataGridViewTriState.False; grid.DefaultCellStyle.WrapMode = DataGridViewTriState.False;
        grid.AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.None; grid.RowTemplate.Height = 26; grid.ScrollBars = ScrollBars.Both;
        grid.AlternatingRowsDefaultCellStyle.BackColor = Color.FromArgb(248, 248, 248);
        for (var column = 0; column < grid.Columns.Count; column++)
        {
            grid.Columns[column].AutoSizeMode = DataGridViewAutoSizeColumnMode.None;
            grid.Columns[column].Width = column switch
            {
                0 => 70,
                1 => 95,
                2 => 110,
                3 => 115,
                4 => 180,
                5 or 6 => 90,
                7 => 105,
                8 or 9 => 80,
                >= 10 and < 25 => 108,
                _ => 108
            };
            grid.Columns[column].HeaderCell.Style.BackColor = column < 10 ? Color.FromArgb(231, 241, 255) : column < 25 ? Color.FromArgb(220, 238, 255) : Color.FromArgb(255, 231, 209);
        }
        void RefreshModules()
        {
        var scroll = grid.HorizontalScrollingOffset;
        grid.Rows.Clear();
        foreach (var m in getModules().Where(module => module.Connected).OrderBy(module => module.Number))
        {
            var rowValues = new List<object?> { $"#{m.Number:00}", m.SoftwareVersion, m.EquipmentId, m.Model, m.Barcode, m.Voltage, m.Current, m.Status, m.Soc, m.Soh }; rowValues.AddRange(m.CellVoltages.Cast<object?>()); rowValues.AddRange(m.CellTemperatures.Cast<object?>());
            var row = grid.Rows.Add(rowValues.ToArray());
            var voltages = m.CellVoltages.Where(value => value.HasValue).Select(value => value!.Value).ToArray();
            var temperatures = m.CellTemperatures.Where(value => value.HasValue).Select(value => value!.Value).ToArray();
            double? maximumVoltage = voltages.Length == 0 ? null : voltages.Max(), minimumVoltage = voltages.Length == 0 ? null : voltages.Min(), maximumTemperature = temperatures.Length == 0 ? null : temperatures.Max();
            for (var index = 0; index < 15; index++)
            {
                var voltageCell = grid[10 + index, row]; voltageCell.Style.BackColor = Color.FromArgb(238, 246, 255);
                if (maximumVoltage.HasValue && m.CellVoltages[index] == maximumVoltage) voltageCell.Style.BackColor = Color.FromArgb(211, 249, 216);
                else if (minimumVoltage.HasValue && m.CellVoltages[index] == minimumVoltage) voltageCell.Style.BackColor = Color.FromArgb(255, 227, 227);
                var temperatureCell = grid[25 + index, row]; temperatureCell.Style.BackColor = Color.FromArgb(255, 247, 237);
                if (m.CellTemperatures[index] >= 60) { temperatureCell.Style.BackColor = Color.FromArgb(255, 77, 77); temperatureCell.Style.ForeColor = Color.White; }
                else if (maximumTemperature.HasValue && m.CellTemperatures[index] == maximumTemperature) temperatureCell.Style.BackColor = Color.FromArgb(255, 249, 196);
            }
        }
        grid.HorizontalScrollingOffset = scroll;
        updated.Text = $"\uC5C5\uB370\uC774\uD2B8: {DateTime.Now:yyyy-MM-dd HH:mm:ss}";
        }
        grid.DefaultCellStyle.NullValue = "-";
        _refreshTimer.Tick += (_, _) => RefreshModules();
        RefreshModules();
        _refreshTimer.Start();
        UiTheme.PreserveCellSelectionColors(grid);
        root.Controls.Add(grid); var ok = UiTheme.Button("OK"); ok.Width = 75; ok.Anchor = AnchorStyles.Right; ok.Click += (_, _) => Close(); root.Controls.Add(ok);
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) _refreshTimer.Dispose();
        base.Dispose(disposing);
    }

    internal static Control CreateCellLegend()
    {
        var legend = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
        legend.Controls.Add(new Label { Text = "셀 전압:", AutoSize = true, Margin = new Padding(0, 6, 3, 0) });
        legend.Controls.Add(LegendLabel(" 최고 ", Color.FromArgb(211, 249, 216), Color.Black));
        legend.Controls.Add(LegendLabel(" 최저 ", Color.FromArgb(255, 227, 227), Color.Black));
        legend.Controls.Add(new Label { Text = "   셀 온도:", AutoSize = true, Margin = new Padding(8, 6, 3, 0) });
        legend.Controls.Add(LegendLabel(" 최고 ", Color.FromArgb(255, 249, 196), Color.Black));
        legend.Controls.Add(LegendLabel(" 60℃ 이상 ", Color.FromArgb(255, 77, 77), Color.White));
        return legend;
    }

    private static Label LegendLabel(string text, Color background, Color foreground) => new() { Text = text, AutoSize = true, BackColor = background, ForeColor = foreground, Margin = new Padding(0, 4, 4, 0), Padding = new Padding(2) };
}

public sealed class ModuleDetailDialog : Form
{
    private readonly System.Windows.Forms.Timer _refreshTimer = new() { Interval = 3000 };

    public ModuleDetailDialog(int moduleNumber, Func<ModuleState?> getModule)
    {
        var module = getModule() ?? new ModuleState { Number = moduleNumber };
        Text = $"모듈 #{module.Number:00} 상세정보"; ClientSize = new Size(540, 650); MinimumSize = new Size(520, 600); StartPosition = FormStartPosition.CenterParent;
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(10), RowCount = 5 }; root.RowStyles.Add(new RowStyle(SizeType.Absolute, 30)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 125)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 34)); root.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 38)); Controls.Add(root);
        var updated = new Label { Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleRight };
        root.Controls.Add(updated);
        var info = new GroupBox { Text = $"모듈 #{module.Number:00} / {module.Model} / {module.Barcode}", Dock = DockStyle.Fill }; var fields = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 3 };
        fields.Controls.Add(new Label { Text = $"1. 전압: {module.Voltage?.ToString("0.0") ?? "-"} V", Dock = DockStyle.Fill }); fields.Controls.Add(new Label { Text = $"2. 전류: {module.Current?.ToString("0.0") ?? "-"} A", Dock = DockStyle.Fill }); fields.Controls.Add(new Label { Text = $"3. 상태: {module.Status}", Dock = DockStyle.Fill }); fields.Controls.Add(new Label { Text = $"4. SOC: {module.Soc?.ToString() ?? "-"} %", Dock = DockStyle.Fill }); fields.Controls.Add(new Label { Text = $"5. SOH: {module.Soh?.ToString() ?? "-"} %", Dock = DockStyle.Fill }); fields.Controls.Add(new Label { Text = $"6. Equip ID: {module.EquipmentId}", ForeColor = Color.Red, Dock = DockStyle.Fill }); info.Controls.Add(fields); root.Controls.Add(info);
        root.Controls.Add(AllModulesDialog.CreateCellLegend());
        var grid = new DataGridView { Dock = DockStyle.Fill, ReadOnly = true }; UiTheme.ConfigureGrid(grid); grid.Columns.Add("cell", "셀"); grid.Columns.Add("voltage", "전압[V]"); grid.Columns.Add("temperature", "온도[℃]"); grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        void RefreshModule()
        {
            var latest = getModule();
            module = latest is { Connected: true } ? latest : new ModuleState { Number = moduleNumber };
            info.Text = $"\uBAA8\uB4C8 #{moduleNumber:00} / {module.Model} / {module.Barcode}";
            fields.Controls[0].Text = $"1. 전압: {module.Voltage?.ToString("0.0") ?? "-"} V";
            fields.Controls[1].Text = $"2. 전류: {module.Current?.ToString("0.0") ?? "-"} A";
            fields.Controls[2].Text = $"3. 상태: {module.Status}";
            fields.Controls[3].Text = $"4. SOC: {module.Soc?.ToString() ?? "-"} %";
            fields.Controls[4].Text = $"5. SOH: {module.Soh?.ToString() ?? "-"} %";
            fields.Controls[5].Text = $"6. Equip ID: {module.EquipmentId}";
            updated.Text = $"\uC5C5\uB370\uC774\uD2B8: {DateTime.Now:yyyy-MM-dd HH:mm:ss}";
            grid.Rows.Clear();
        var valid = module.CellVoltages.Where(v => v.HasValue).Select(v => v!.Value).ToArray(); double? max = valid.Length > 0 ? valid.Max() : null, min = valid.Length > 0 ? valid.Min() : null;
        var temperatures = module.CellTemperatures.Where(t => t.HasValue).Select(t => t!.Value).ToArray();
        double? maxTemperature = temperatures.Length > 0 ? temperatures.Max() : null;
        grid.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(231, 241, 255);
        for (var i = 0; i < 15; i++)
        {
            var row = grid.Rows.Add($"Cell {i + 1:00}", module.CellVoltages[i]?.ToString("0.00") ?? "-", module.CellTemperatures[i]?.ToString("0.0") ?? "-");
            if (max.HasValue && module.CellVoltages[i] == max) grid[1, row].Style.BackColor = Color.FromArgb(211, 249, 216);
            else if (min.HasValue && module.CellVoltages[i] == min) grid[1, row].Style.BackColor = Color.FromArgb(255, 227, 227);
            if (module.CellTemperatures[i] >= 60) { grid[2, row].Style.BackColor = Color.FromArgb(255, 77, 77); grid[2, row].Style.ForeColor = Color.White; }
            else if (maxTemperature.HasValue && module.CellTemperatures[i] == maxTemperature) grid[2, row].Style.BackColor = Color.FromArgb(255, 249, 196);
        }
        }
        _refreshTimer.Tick += (_, _) => RefreshModule();
        RefreshModule();
        _refreshTimer.Start();
        UiTheme.PreserveCellSelectionColors(grid);
        root.Controls.Add(grid); var ok = UiTheme.Button("OK"); ok.Width = 75; ok.Anchor = AnchorStyles.Right; ok.Click += (_, _) => Close(); root.Controls.Add(ok);
    }
    protected override void Dispose(bool disposing)
    {
        if (disposing) _refreshTimer.Dispose();
        base.Dispose(disposing);
    }

}

public sealed class ActiveAlarmDialog : Form
{
    private static readonly string[] AlarmNames =
    [
        "Battery Fuse Broken", "Lithium battery Missing", "Lithium battery communication failure",
        "Lithium battery communication has failed.", "All Lithium Battery Communication Failure",
        "Upgrade Failed", "Low temperature protection", "Low temperature discharge",
        "High temperature protection", "Charging overvoltage", "Overcharge", "Overdischarge",
        "Overcharge Protection", "Overdischarge Protection", "Charging Overcurrent Protection",
        "Heavy load Overcurrent Protection", "Discharge Overcurrent Protection", "Upgrade failure",
        "Busbar overvoltage protection", "Input reverse connection", "Abnormal shutdown",
        "Unlock failure", "Board hardware fault", "BMU Missing", "Lithium Battery Protection",
        "Discharge Low Temperature", "Charge Overcurrent Protection",
        "Discharge High Temperature Protection", "Charge High Temperature Protection",
        "Discharge Low Temperature Protection", "Charge Low Temperature Protection",
        "High Battery Temperature", "Low Battery Temperature", "Low Temperature",
        "Overall Lithium Battery Protection", "Overvoltage Protection", "Undervoltage Protection",
        "Cell 1 Fault", "Cell 2 Fault", "Cell 3 Fault", "Cell 4 Fault", "Cell 5 Fault",
        "Cell 6 Fault", "Cell 7 Fault", "Cell 8 Fault", "Cell 9 Fault", "Cell 10 Fault",
        "Cell 11 Fault", "Cell 12 Fault", "Cell 13 Fault", "Cell 14 Fault", "Cell 15 Fault"
    ];
    public ActiveAlarmDialog(IReadOnlyList<ActiveAlarmEntry>? active = null)
    {
        Text = "Active Alarm List"; WindowState = FormWindowState.Maximized;
        var grid = new DataGridView { Dock = DockStyle.Fill, ReadOnly = true }; UiTheme.ConfigureGrid(grid); grid.Columns.Add("alarm", "Active Alarm list"); grid.Columns.Add("system", "시스템"); for (var n = 1; n <= 10; n++) grid.Columns.Add($"m{n}", $"모듈-{n}"); grid.Columns[0].Width = 240;
        grid.DefaultCellStyle.WrapMode = DataGridViewTriState.True;
        grid.AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.AllCells;
        grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.AllCells;
        grid.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(231, 241, 255);
        UiTheme.PreserveCellSelectionColors(grid);
        var undefinedRows = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        foreach (var name in AlarmNames) grid.Rows.Add(name);
        if (active is not null)
        {
            foreach (var alarm in active)
            {
                var alarmText = alarm.Text.Trim();
                var row = Array.FindIndex(AlarmNames,
                    name => alarmText.Contains(name, StringComparison.OrdinalIgnoreCase));
                var undefined = row < 0;
                if (undefined && !undefinedRows.TryGetValue(alarmText, out row))
                {
                    row = grid.Rows.Add(alarmText.Length == 0 ? "(Alarm Text \uC5C6\uC74C)" : alarmText);
                    undefinedRows[alarmText] = row;
                    grid.Rows[row].DefaultCellStyle.BackColor = Color.FromArgb(233, 236, 239);
                }
                var column = alarm.ModuleNo is >= 1 and <= 10 ? alarm.ModuleNo.Value + 1 : 1;
                var levelText = alarm.Level == AlarmLevel.Normal ? "Unknown" : alarm.Level.ToString();
                grid[column, row].Value = $"{alarm.Time}\n({levelText})";
                grid[column, row].Style.BackColor = undefined ? Color.FromArgb(233, 236, 239) : alarm.Level switch
                {
                    AlarmLevel.Critical => Color.FromArgb(255, 77, 79),
                    AlarmLevel.Major => Color.FromArgb(255, 169, 64),
                    AlarmLevel.Minor => Color.FromArgb(255, 214, 102),
                    AlarmLevel.Warning => Color.FromArgb(145, 213, 255),
                    _ => Color.White
                };
            }
        }
        Controls.Add(grid);
    }
}

public sealed class AlarmDefinitionDialog : Form
{
    private static readonly (string Name, string Description)[] Definitions =
    [
        ("Battery Fuse Broken", "축전지 내부 퓨즈 단선으로 전류 공급이 차단된 상태"),
        ("Lithium battery Missing", "SMU 재시작 후 이전보다 적은 수의 축전지가 감지된 상태"),
        ("Lithium battery communication failure", "축전지와 SMU02C 또는 IoT 장비 간 통신이 불가능한 상태"),
        ("Lithium battery communication has failed.", "축전지와 SMU02C 또는 IoT 장비 간 통신이 불가능한 상태"),
        ("All Lithium Battery Communication Failure", "전체 축전지와 SMU02C 또는 IoT 장비 간 통신이 불가능한 상태"),
        ("Upgrade Failed", "축전지 모듈 펌웨어 업그레이드가 정상적으로 완료되지 않은 상태"),
        ("Low temperature protection", "저온 환경에서 축전지를 보호하기 위해 보호 모드가 활성화된 상태"),
        ("Low temperature discharge", "저온 상태에서 방전 성능 저하 또는 방전 제한이 발생한 상태"),
        ("High temperature protection", "고온 환경에서 축전지를 보호하기 위해 보호 모드가 활성화된 상태"),
        ("Charging overvoltage", "충전 전압이 허용 범위를 초과한 상태"),
        ("Overcharge", "축전지가 허용된 최대 전압/용량 이상으로 충전된 상태"),
        ("Overdischarge", "축전지가 허용된 최소 전압/용량 이하로 방전된 상태"),
        ("Overcharge Protection", "과충전 상태로 인해 보호 모드가 활성화된 상태"),
        ("Overdischarge Protection", "과방전 상태로 인해 보호 모드가 활성화된 상태"),
        ("Charging Overcurrent Protection", "충전 전류가 허용 범위를 초과하여 보호 모드가 활성화된 상태"),
        ("Heavy load Overcurrent Protection", "부하 증가로 인해 과전류 보호 모드가 활성화된 상태"),
        ("Discharge Overcurrent Protection", "방전 전류가 허용 범위를 초과하여 보호 모드가 활성화된 상태"),
        ("Upgrade failure", "축전지 BMS 펌웨어 업그레이드가 실패한 상태"),
        ("Busbar overvoltage protection", "축전지 버스바 전압이 허용 범위를 초과하여 보호 모드가 활성화된 상태"),
        ("Input reverse connection", "축전지 입력 전압의 극성이 반대로 연결된 상태"),
        ("Abnormal shutdown", "축전지 시스템이 비정상적으로 종료된 상태"),
        ("Unlock failure", "축전지 잠금 해제 명령이 실패한 상태"),
        ("Board hardware fault", "BMS 제어 보드의 하드웨어 오류가 발생한 상태 (모듈 교체 필요)"),
        ("BMU Missing", "축전지 모듈 인식 불가 상태 (전원 또는 통신 이상)"),
        ("Lithium Battery Protection", "축전지 보호 모드가 동작하여 충·방전이 차단된 상태"),
        ("Discharge Low Temperature", "저온 상태로 인해 방전 성능 저하 또는 방전 제한이 발생한 상태"),
        ("Charge Overcurrent Protection", "충전 중 과전류로 인해 보호 모드가 활성화된 상태"),
        ("Discharge High Temperature Protection", "방전 중 고온(65℃ 이상) 상태로 인해 보호 모드가 활성화된 상태"),
        ("Charge High Temperature Protection", "충전 중 고온(60℃ 이상) 상태로 인해 보호 모드가 활성화된 상태"),
        ("Discharge Low Temperature Protection", "방전 중 저온(-20℃ 이하) 상태로 인해 보호 모드가 활성화된 상태"),
        ("Charge Low Temperature Protection", "충전 중 저온(0℃ 이하) 상태로 인해 보호 모드가 활성화된 상태"),
        ("High Battery Temperature", "축전지 온도가 허용 기준 이상으로 상승한 상태"),
        ("Low Battery Temperature", "축전지 온도가 허용 기준 이하로 저하된 상태"),
        ("Low Temperature", "주변 또는 축전지 온도가 낮아 성능 저하가 발생할 수 있는 상태"),
        ("Overall Lithium Battery Protection", "축전지 전체에 대한 보호 모드가 활성화된 상태 (시스템 레벨 차단)"),
        ("Overvoltage Protection", "최대 셀 전압이 3.8V를 초과한 상태"),
        ("Undervoltage Protection", "최소 셀 전압이 2.5V 미만인 상태")
    ];

    public AlarmDefinitionDialog()
    {
        Text = "정의된 알람 리스트"; StartPosition = FormStartPosition.CenterParent; ClientSize = new Size(850, 600); MinimumSize = new Size(650, 450);
        var grid = new DataGridView { Dock = DockStyle.Fill, ReadOnly = true }; UiTheme.ConfigureGrid(grid); grid.Columns.Add("alarm", "Alarm Name"); grid.Columns.Add("description", "Description");
        grid.Columns[0].Width = 300; grid.Columns[1].AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill; grid.DefaultCellStyle.WrapMode = DataGridViewTriState.True; grid.AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.AllCells;
        foreach (var definition in Definitions) grid.Rows.Add(definition.Name, definition.Description);
        for (var cell = 1; cell <= 15; cell++) grid.Rows.Add($"Cell {cell} Fault", $"셀 {cell} 이상 상태 발생 (모듈 교체 필요)");
        Controls.Add(grid);
    }
}

public sealed class EpoProgressDialog : Form
{
    private readonly DataGridView _grid = new(); private readonly ProgressBar _progress = new(); private readonly Button _close = UiTheme.Button("진행 중..."); private int _completed;
    public EpoProgressDialog(IReadOnlyList<int> modules, string operation)
    {
        Text = $"{operation} 진행상태"; ClientSize = new Size(430, Math.Min(500, 170 + modules.Count * 30)); StartPosition = FormStartPosition.CenterParent; ControlBox = false;
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(12), RowCount = 4 }; root.RowStyles.Add(new RowStyle(SizeType.Absolute, 35)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 28)); root.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 36)); Controls.Add(root);
        root.Controls.Add(new Label { Text = $"모듈별 강제 {operation} 진행상태", Font = new Font("맑은 고딕", 11F, FontStyle.Bold), Dock = DockStyle.Fill }); _progress.Dock = DockStyle.Fill; _progress.Maximum = modules.Count; root.Controls.Add(_progress);
        UiTheme.ConfigureGrid(_grid); _grid.Dock = DockStyle.Fill; _grid.ReadOnly = true; _grid.Columns.Add("module", "모듈"); _grid.Columns.Add("status", "진행상태"); _grid.Columns.Add("time", "처리시각");
        _grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.None; _grid.Columns[0].Width = 70; _grid.Columns[1].AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill; _grid.Columns[2].Width = 90;
        foreach (var n in modules) _grid.Rows.Add($"#{n:00}", "대기", "-"); root.Controls.Add(_grid);
        _close.Dock = DockStyle.Right; _close.Width = 100; _close.Enabled = false; _close.Click += (_, _) => Close(); root.Controls.Add(_close);
    }
    public void UpdateModule(int module, string status, string? detail)
    {
        var row = _grid.Rows.Cast<DataGridViewRow>().First(r => Equals(r.Cells[0].Value, $"#{module:00}")); row.Cells[1].Value = status; row.Cells[1].ToolTipText = detail ?? "";
        row.DefaultCellStyle.BackColor = status switch { "성공" => Color.FromArgb(220, 252, 231), "실패" => Color.FromArgb(254, 226, 226), "진행 중" => Color.FromArgb(219, 234, 254), _ => Color.White };
        row.DefaultCellStyle.ForeColor = status switch { "성공" => Color.FromArgb(22, 101, 52), "실패" => Color.FromArgb(153, 27, 27), "진행 중" => Color.FromArgb(29, 78, 216), _ => Color.FromArgb(100, 116, 139) };
        if (status is "성공" or "실패") { row.Cells[2].Value = DateTime.Now.ToString("HH:mm:ss"); _progress.Value = Math.Min(_progress.Maximum, ++_completed); } Application.DoEvents();
    }
    public void Complete() { ControlBox = true; _close.Text = "닫기"; _close.Enabled = true; }
}

public sealed class SlaveListDialog : Form
{
    private readonly SlaveCoordinator _coordinator; private readonly ListBox _list = new(); private readonly System.Windows.Forms.Timer _timer = new() { Interval = 5000 };
    public SlaveListDialog(SlaveCoordinator coordinator)
    {
        _coordinator = coordinator; Text = "Slave 목록"; ClientSize = new Size(850, 400); StartPosition = FormStartPosition.CenterParent;
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(10), RowCount = 2 }; root.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 36)); Controls.Add(root); _list.Dock = DockStyle.Fill; root.Controls.Add(_list);
        var refresh = UiTheme.Button("업데이트"); refresh.Width = 90; refresh.Click += (_, _) => RefreshList(); var close = UiTheme.Button("OK"); close.Width = 75; close.Click += (_, _) => Close(); var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft }; buttons.Controls.Add(close); buttons.Controls.Add(refresh); root.Controls.Add(buttons);
        _timer.Tick += (_, _) => RefreshList(); _timer.Start(); FormClosed += (_, _) => _timer.Stop(); RefreshList();
    }
    private void RefreshList()
    {
        _list.Items.Clear(); foreach (var slave in _coordinator.GetStatuses()) { var prefix = slave.IsAlive ? "(alive)" : "(-)"; var index = _list.Items.Add($"{prefix} {slave.Profile} | 대상: {slave.TargetIp} | 등록상태: 127.0.0.1:{slave.Port} | 시스템: {slave.SystemName}"); if (index >= 0) { /* WinForms ListBox는 항목별 색상 대신 상태 문자열을 명시 */ } }
    }
}

public sealed class ChargeLimitDialog : Form
{
    private readonly NumericUpDown _value = new() { DecimalPlaces = 2, Minimum = 0.05M, Maximum = 1.00M, Increment = 0.05M, Dock = DockStyle.Fill };
    public int SnmpValue => decimal.ToInt32(_value.Value * 100);
    public ChargeLimitDialog(int current)
    {
        Text = "충전전류제한 설정"; ClientSize = new Size(330, 135); FormBorderStyle = FormBorderStyle.FixedDialog; StartPosition = FormStartPosition.CenterParent; MaximizeBox = false; _value.Value = Math.Clamp(current / 100M, _value.Minimum, _value.Maximum);
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(14), RowCount = 3 }; root.Controls.Add(new Label { Text = "충전전류제한 설정 (0.05 ~ 1.00[C])", Dock = DockStyle.Fill }); root.Controls.Add(_value); var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft }; var cancel = UiTheme.Button("취소"); cancel.DialogResult = DialogResult.Cancel; var ok = UiTheme.Button("OK"); ok.DialogResult = DialogResult.OK; buttons.Controls.Add(cancel); buttons.Controls.Add(ok); root.Controls.Add(buttons); Controls.Add(root); AcceptButton = ok; CancelButton = cancel;
    }
}

public sealed class SocLimitDialog : Form
{
    private readonly RadioButton _r90 = new() { Text = "90%", AutoSize = true }, _r95 = new() { Text = "95%", AutoSize = true }, _r100 = new() { Text = "100%", AutoSize = true }, _unused = new() { Text = "사용안함", AutoSize = true };
    public int EnabledValue => _unused.Checked ? 1 : 2; public int? LimitValue => _unused.Checked ? null : _r90.Checked ? 90 : _r95.Checked ? 95 : 100;
    public SocLimitDialog(int enabled, int value)
    {
        Text = "SOC충전제한 설정"; ClientSize = new Size(300, 210); FormBorderStyle = FormBorderStyle.FixedDialog; StartPosition = FormStartPosition.CenterParent; MaximizeBox = false;
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(18), RowCount = 6 }; root.Controls.Add(new Label { Text = "SOC충전제한 설정", Font = new Font("맑은 고딕", 10F, FontStyle.Bold), Dock = DockStyle.Fill }); foreach (var radio in new[] { _r90, _r95, _r100, _unused }) root.Controls.Add(radio); if (enabled == 1) _unused.Checked = true; else if (value == 95) _r95.Checked = true; else if (value == 100) _r100.Checked = true; else _r90.Checked = true;
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft }; var cancel = UiTheme.Button("취소"); cancel.DialogResult = DialogResult.Cancel; var ok = UiTheme.Button("OK"); ok.DialogResult = DialogResult.OK; buttons.Controls.Add(cancel); buttons.Controls.Add(ok); root.Controls.Add(buttons); Controls.Add(root); AcceptButton = ok; CancelButton = cancel;
    }
}
