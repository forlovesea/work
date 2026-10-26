using TBC1000B.WinForms.Models;
using TBC1000B.WinForms.Services;

namespace TBC1000B.WinForms.Views;

public sealed class OperationRecordDialog : Form
{
    private readonly OperationRecordService _recorder;
    private readonly ChargeDischargeRecordService _events;
    private readonly Func<MonitorSnapshot?> _snapshotProvider;
    private readonly Label _status = new(), _eventStatus = new(), _limits = new();
    private readonly Label _eventHeadingStatus = new() { Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft, Name = "EventRecordingState" };
    private readonly CheckBox _charge = new() { Text = "충전 이벤트 사용", AutoSize = true };
    private readonly CheckBox _discharge = new() { Text = "방전 이벤트 사용", AutoSize = true };
    private readonly NumericUpDown _chargeThreshold = new() { Minimum = 0.1m, Maximum = decimal.MaxValue, DecimalPlaces = 1, Increment = 0.1m, Dock = DockStyle.Fill };
    private readonly NumericUpDown _dischargeThreshold = new() { Minimum = 1, Maximum = 90, Value = 1, Dock = DockStyle.Fill };
    private readonly ComboBox _chargeInterval = Intervals(), _dischargeInterval = Intervals();
    private readonly System.Windows.Forms.Timer _statusTimer = new() { Interval = 1000 };
    private decimal? _knownChargeMaximum;

    public OperationRecordDialog(OperationRecordService recorder, Func<MonitorSnapshot?> snapshotProvider, ChargeDischargeRecordService events)
    {
        _recorder = recorder; _snapshotProvider = snapshotProvider; _events = events;
        Text = "운전 데이터 / 충방전 이벤트 기록 설정";
        ClientSize = new Size(620, 830); MinimumSize = new Size(580, 520);
        StartPosition = FormStartPosition.CenterParent; MaximizeBox = false;
        var scroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true };
        var root = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 1, Padding = new Padding(14) };
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); scroll.Controls.Add(root); Controls.Add(scroll);
        var blue = Color.FromArgb(234, 243, 255); var mint = Color.FromArgb(232, 248, 239);
        var operation = new TableLayoutPanel { Dock = DockStyle.Fill, Height = 310, ColumnCount = 1, RowCount = 4, Padding = new Padding(12), BackColor = blue };
        operation.RowStyles.Add(new RowStyle(SizeType.Absolute, 30)); operation.RowStyles.Add(new RowStyle(SizeType.Absolute, 66));
        operation.RowStyles.Add(new RowStyle(SizeType.Absolute, 36)); operation.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        operation.Controls.Add(Heading("운전 데이터 기록 주기"));
        var settings = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 2 };
        settings.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 110)); settings.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        var intervalInput = new ComboBox { Dock = DockStyle.Fill, DropDownStyle = ComboBoxStyle.DropDownList, Items = { "1분", "5분", "10분", "30분", "60분" }, SelectedIndex = 1 };
        var durationInput = new DayNumericUpDown { Dock = DockStyle.Fill, Minimum = 1, Maximum = 30, Value = 30 };
        settings.Controls.Add(LabelFor("기록 간격"), 0, 0); settings.Controls.Add(intervalInput, 1, 0);
        settings.Controls.Add(LabelFor("기록 기간"), 0, 1); settings.Controls.Add(durationInput, 1, 1); operation.Controls.Add(settings);
        var title = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
        title.Controls.Add(new Label { Text = "Excel 기록 항목", AutoSize = true, Margin = new Padding(3, 8, 20, 0) });
        var all = UiTheme.Button("전체선택"); var clear = UiTheme.Button("전체해제"); all.Width = clear.Width = 90;
        title.Controls.AddRange([all, clear]); operation.Controls.Add(title);
        var checks = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 6 };
        checks.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50)); checks.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        var boxes = OperationRecordService.FieldSpecs.Select(s => new CheckBox { Text = s.Label, Tag = s.Key, Checked = true, AutoSize = true }).ToArray();
        for (var i = 0; i < boxes.Length; i++) checks.Controls.Add(boxes[i], i % 2, i / 2);
        all.Click += (_, _) => Array.ForEach(boxes, b => b.Checked = true); clear.Click += (_, _) => Array.ForEach(boxes, b => b.Checked = false);
        operation.Controls.Add(checks); Add(root, operation, 310);

        // Directly below the final EPO checkbox, separate from periodic operating data.
        var eventPanel = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 5, BackColor = mint, Padding = new Padding(12) };
        foreach (var height in new[] { 32, 93, 57, 36, 46 }) eventPanel.RowStyles.Add(new RowStyle(SizeType.Absolute, height));
        var eventHeading = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, Margin = Padding.Empty };
        eventHeading.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 210)); eventHeading.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        eventHeading.Controls.Add(Heading("충방전 이벤트 기록"), 0, 0); eventHeading.Controls.Add(_eventHeadingStatus, 1, 0);
        eventPanel.Controls.Add(eventHeading);
        var grid = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3, RowCount = 3 };
        grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 25));
        grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 31));
        grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 31));
        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 175)); grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 60)); grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 40));
        grid.Controls.Add(LabelFor("이벤트 사용"), 0, 0); grid.Controls.Add(LabelFor("Threshold (임계값)"), 1, 0); grid.Controls.Add(LabelFor("기록 간격"), 2, 0);
        grid.Controls.Add(_discharge, 0, 1); grid.Controls.Add(WithUnit(_dischargeThreshold, "%"), 1, 1); grid.Controls.Add(_dischargeInterval, 2, 1);
        grid.Controls.Add(_charge, 0, 2); grid.Controls.Add(WithUnit(_chargeThreshold, "A"), 1, 2); grid.Controls.Add(_chargeInterval, 2, 2); eventPanel.Controls.Add(grid);
        _limits.Dock = DockStyle.Fill; _limits.ForeColor = Color.DarkSlateGray; eventPanel.Controls.Add(_limits);
        var eventStart = UiTheme.Button("이벤트 기록시작", Color.FromArgb(16, 164, 83)); eventStart.Width = 160; eventStart.Name = "EventActionButton";
        var eventStop = UiTheme.Button("이벤트 기록중지"); eventStop.Width = 140;
        var applyBar = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false }; applyBar.Controls.AddRange([eventStart, eventStop]); eventPanel.Controls.Add(applyBar);
        _eventStatus.Dock = DockStyle.Fill; _eventStatus.ForeColor = Color.DarkGreen; eventPanel.Controls.Add(_eventStatus); Add(root, eventPanel, 290);

        Add(root, new Label { Text = $"공통 저장 위치: {recorder.OutputDirectory}\n이벤트 파일: 충방전 이벤트 기록.csv (기존 운전 Excel과 별도)", Dock = DockStyle.Fill, Padding = new Padding(8), BackColor = Color.FromArgb(248, 248, 250) }, 82);
        _status.Dock = DockStyle.Fill; Add(root, _status, 30);
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
        var start = UiTheme.Button("운전 기록시작", Color.FromArgb(16, 164, 83)); start.Width = 130;
        var stop = UiTheme.Button("운전 기록중지"); stop.Width = 130;
        var close = UiTheme.Button("닫기"); close.Width = 90; close.Click += (_, _) => Close(); buttons.Controls.AddRange([start, stop, close]); Add(root, buttons, 45);
        void UpdateOperation()
        {
            start.Enabled = !_recorder.IsRecording; stop.Enabled = _recorder.IsRecording;
            settings.Enabled = title.Enabled = checks.Enabled = !_recorder.IsRecording;
            _status.Text = _recorder.IsRecording ? $"● 운전 데이터 기록 중 · 종료 {_recorder.EndsAt:MM.dd HH:mm}" : "운전 데이터 기록 중지";
        }
        start.Click += (_, _) =>
        {
            try
            {
                if (_snapshotProvider()?.Connection != ConnectionState.Connected) throw new InvalidOperationException("먼저 축전지 시스템에 접속해 주세요.");
                var fields = boxes.Where(b => b.Checked).Select(b => (string)b.Tag!).ToHashSet(StringComparer.Ordinal);
                var interval = new[] { 1, 5, 10, 30, 60 }[intervalInput.SelectedIndex];
                _recorder.Start(new OperationRecordOptions(interval, (int)durationInput.Value, fields), _snapshotProvider); UpdateOperation();
            }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "운전 기록 시작 불가", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        };
        stop.Click += (_, _) => { _recorder.Stop(); UpdateOperation(); };
        var saved = events.Options;
        _charge.Checked = saved.ChargeEnabled; _discharge.Checked = saved.DischargeEnabled;
        _dischargeThreshold.Value = saved.DischargeThresholdPercent;
        _chargeInterval.SelectedIndex = saved.ChargeIntervalMinutes / 5 - 1; _dischargeInterval.SelectedIndex = saved.DischargeIntervalMinutes / 5 - 1;
        RefreshLimits(); _chargeThreshold.Value = Math.Clamp(saved.ChargeThresholdAmps, _chargeThreshold.Minimum, _chargeThreshold.Maximum);
        ChargeDischargeRecordOptions CurrentOptions() => new(_charge.Checked, _chargeThreshold.Value, (_chargeInterval.SelectedIndex + 1) * 5,
            _discharge.Checked, _dischargeThreshold.Value, (_dischargeInterval.SelectedIndex + 1) * 5);
        void UpdateEvents()
        {
            var running = _events.IsMonitoring;
            _eventHeadingStatus.Text = "● " + _events.StateText;
            _eventHeadingStatus.ForeColor = running ? Color.DarkGreen : Color.DimGray;
            _eventStatus.Text = _events.Status + "\n기본값 자동 시작 · 설정 변경 후 적용 · 중지 후 시작으로 재개";
            eventStart.Text = running ? "설정 변경 적용" : "이벤트 기록시작";
            eventStart.Enabled = running ? CurrentOptions() != _events.Options : _charge.Checked || _discharge.Checked;
            eventStop.Enabled = running;
        }
        _charge.CheckedChanged += (_, _) => { RefreshEnabled(); UpdateEvents(); };
        _discharge.CheckedChanged += (_, _) => { RefreshEnabled(); UpdateEvents(); }; RefreshEnabled();
        _chargeThreshold.ValueChanged += (_, _) => UpdateEvents(); _dischargeThreshold.ValueChanged += (_, _) => UpdateEvents();
        _chargeInterval.SelectedIndexChanged += (_, _) => UpdateEvents(); _dischargeInterval.SelectedIndexChanged += (_, _) => UpdateEvents();
        eventStart.Click += (_, _) =>
        {
            try
            {
                var snapshot = _snapshotProvider(); var sample = snapshot is null ? null : BatteryEventSample.Read(snapshot);
                if (_events.IsMonitoring) { _events.Configure(CurrentOptions(), sample); _events.Observe(sample); }
                else _events.Start(CurrentOptions(), sample);
                UpdateEvents();
            }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "이벤트 설정 확인", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        };
        eventStop.Click += (_, _) => { _events.Stop(); UpdateEvents(); };
        _statusTimer.Tick += (_, _) => { RefreshLimits(); UpdateOperation(); UpdateEvents(); };
        _statusTimer.Start(); UpdateOperation(); UpdateEvents();
        FormClosed += (_, _) => { _statusTimer.Stop(); _statusTimer.Dispose(); };
    }

    private void RefreshLimits()
    {
        var snapshot = _snapshotProvider(); var sample = snapshot is null ? null : BatteryEventSample.Read(snapshot);
        var maximum = snapshot is null ? null : BatteryEventSample.ReadChargeMaximumAmps(snapshot);
        if (maximum is >= 0.1m)
        {
            _knownChargeMaximum = maximum;
            _chargeThreshold.Maximum = maximum.Value;
        }
        // Missing telemetry must not disable editing or reset the user's draft.
        _limits.Text = sample is null ? (_knownChargeMaximum is { } known
            ? $"충전 입력 범위: 0.1~{known:0.0}A (마지막 확인 상한)\n전류·SOC 등 측정값 수신 대기 · 적용 시 최신 값 재검증"
            : "충전 상한 미확인 · 체크 후 임계값·간격을 미리 입력할 수 있습니다.\n총용량·충전전류제한(C) 확인 전에는 설정을 적용할 수 없습니다.")
            : $"총용량 {sample.CapacityAh:0.0}Ah · 방전: 총용량 × 설정 % (1~90%)\n충전: 0.1~{sample.ChargeMaximumAmps:0.0}A (총용량 × {sample.ChargeLimitC:0.00}C) · 간격 5~30분";
        RefreshEnabled();
    }
    private void RefreshEnabled()
    {
        _chargeThreshold.Enabled = _chargeInterval.Enabled = _charge.Checked;
        _dischargeThreshold.Enabled = _dischargeInterval.Enabled = _discharge.Checked;
    }
    private static ComboBox Intervals() => new() { Dock = DockStyle.Fill, DropDownStyle = ComboBoxStyle.DropDownList,
        Items = { "5분", "10분", "15분", "20분", "25분", "30분" }, SelectedIndex = 0 };
    private static Label Heading(string text) => new() { Text = text, Font = new Font("맑은 고딕", 11F, FontStyle.Bold), Dock = DockStyle.Fill };
    private static Label LabelFor(string text) => new() { Text = text, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft };
    private static Control WithUnit(Control input, string unit)
    {
        var panel = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, GrowStyle = TableLayoutPanelGrowStyle.FixedSize, Margin = Padding.Empty };
        panel.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); panel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 28));
        panel.Controls.Add(input, 0, 0); panel.Controls.Add(LabelFor(unit), 1, 0); return panel;
    }
    private static void Add(TableLayoutPanel panel, Control control, int height)
    {
        var row = panel.RowStyles.Count; panel.RowCount = row + 1; panel.RowStyles.Add(new RowStyle(SizeType.Absolute, height)); panel.Controls.Add(control, 0, row);
    }
}
