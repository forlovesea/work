namespace SafeChild;

internal sealed class DomainScheduleDialog : Form
{
    private readonly CheckBox _enabled = new() { Text = "시간 적용", AutoSize = true };
    private readonly ComboBox _type = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 250 };
    private readonly DateTimePicker _start = DatePicker();
    private readonly DateTimePicker _end = DatePicker();
    private readonly NumericUpDown _minutes = new() { Minimum = 1, Maximum = 525600, Width = 120 };
    private readonly CheckBox _restart = new() { Text = "저장 시 Walltime을 지금부터 다시 시작", AutoSize = true };
    private readonly DomainSchedule _original;
    private readonly CheckBox _weekdayEnabled = new() { Text = "사용", AutoSize = true };
    private readonly CheckBox _weekendEnabled = new() { Text = "사용", AutoSize = true };
    private readonly DateTimePicker _weekdayStart = TimePicker();
    private readonly DateTimePicker _weekdayEnd = TimePicker();
    private readonly DateTimePicker _weekendStart = TimePicker();
    private readonly DateTimePicker _weekendEnd = TimePicker();
    private readonly CheckBox _individual = new() { Text = "월~일 각각 설정", AutoSize = true };
    private readonly List<(CheckBox Enabled, DateTimePicker Start, DateTimePicker End)> _days = [];
    private readonly FlowLayoutPanel _dailyPanel = new() { AutoSize = true, FlowDirection = FlowDirection.TopDown, WrapContents = false };
    private readonly List<(Control Label, Control Input, int Type)> _typeRows = [];
    private Control _walltimeHelp = null!;
    private Control _restartHelp = null!;
    private Control _weeklyHelp = null!;
    public DomainSchedule? Result { get; private set; }

    public DomainScheduleDialog(string domain, DomainSchedule original)
    {
        _original = original;
        Text = $"시간 설정 - {domain}";
        Font = new Font("맑은 고딕", 9F);
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; MinimizeBox = false; ShowInTaskbar = false;
        ClientSize = new Size(690, 780);
        BackColor = Color.White;
        ForeColor = Color.FromArgb(30, 41, 59);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 9, Padding = new Padding(20), AutoScroll = true };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 190));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        for (var row = 0; row < 9; row++) layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        _type.Items.AddRange(["절대 시간 (시작 ~ 종료)", "Walltime (경과 시간)", "반복 시간 (요일별)"]);
        _enabled.Checked = original.Enabled;
        _type.SelectedIndex = Math.Clamp((int)original.Type, 0, 2);
        _start.Value = original.Start.LocalDateTime;
        _end.Value = original.End.LocalDateTime;
        _minutes.Value = Math.Clamp(original.WalltimeMinutes, 1, 525600);
        AddRow(layout, 0, "활성화", _enabled);
        AddRow(layout, 1, "시간 타입", _type);
        AddTypeRow(layout, 2, "시작 (PC 현지 시각)", _start, 0);
        AddTypeRow(layout, 3, "종료 (PC 현지 시각)", _end, 0);
        AddTypeRow(layout, 4, "Walltime (분)", _minutes, 1);
        AddTypeRow(layout, 5, "다시 시작", _restart, 1);
        AddTypeRow(layout, 6, "평일 (월~금)", WindowInputs(_weekdayEnabled, _weekdayStart, _weekdayEnd, original.Weekdays), 2);
        AddTypeRow(layout, 7, "주말 (토·일)", WindowInputs(_weekendEnabled, _weekendStart, _weekendEnd, original.Weekends), 2);
        var weekly = new FlowLayoutPanel { AutoSize = true, FlowDirection = FlowDirection.TopDown, WrapContents = false };
        _individual.Checked = original.Days is { Length: 7 };
        weekly.Controls.Add(_individual);
        for (var i = 0; i < 7; i++)
        {
            var enabled = new CheckBox { Text = "일월화수목금토"[i] + "요일", AutoSize = true };
            var start = TimePicker(); var end = TimePicker();
            _days.Add((enabled, start, end));
            _dailyPanel.Controls.Add(WindowInputs(enabled, start, end, original.WindowFor((DayOfWeek)i)));
            enabled.CheckedChanged += (_, _) => UpdateInputs();
        }
        weekly.Controls.Add(_dailyPanel);
        var help = new TableLayoutPanel
        {
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Dock = DockStyle.Top,
            ColumnCount = 1, RowCount = 5, Margin = new Padding(0, 14, 0, 8)
        };
        help.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        help.Controls.Add(HelpCard("시간 적용을 끄면", "예약 시간과 관계없이 목록의 ‘차단 선택’ 상태를 따릅니다.",
            Color.FromArgb(241, 245, 249), Color.FromArgb(51, 65, 85)), 0, 0);
        _walltimeHelp = HelpCard("Walltime · 다시 시작", "체크 후 저장하면 지금부터 설정한 시간 전체를 다시 계산합니다.\n예: 60분 설정에서 20분이 남아 있어도, 저장 후 다시 60분이 됩니다.",
            Color.FromArgb(239, 246, 255), Color.FromArgb(29, 78, 216));
        _restartHelp = HelpCard("남은 시간이 유지되는 경우", "같은 설정을 ‘다시 시작’ 체크 없이 저장하면 남은 시간을 유지합니다.\n단, 시간 적용을 새로 켜거나 타입·분 값을 바꾸면 새로 시작합니다.",
            Color.FromArgb(255, 251, 235), Color.FromArgb(146, 64, 14));
        _weeklyHelp = HelpCard("매주 반복 · PC 현지 시각 기준", "지정한 시간 동안 차단하고, 시간이 지나면 자동 해제합니다.\n‘사용’을 끈 요일 그룹은 새 차단 일정을 시작하지 않습니다.\n종료가 시작보다 이르면 다음 날까지 이어집니다.\n예: 금요일 22:00~07:00은 토요일 아침 07:00까지 적용됩니다.\n시작과 종료가 같으면 해당 요일은 종일 차단합니다.\n반복 일정은 PC 날짜·시각 변경의 영향을 받습니다.",
            Color.FromArgb(240, 253, 250), Color.FromArgb(15, 118, 110));
        help.Controls.Add(_walltimeHelp, 0, 1);
        help.Controls.Add(_restartHelp, 0, 2);
        help.Controls.Add(_weeklyHelp, 0, 3);
        help.Controls.Add(weekly, 0, 4);
        _typeRows.Add((weekly, weekly, 2));
        layout.Controls.Add(help, 0, 8); layout.SetColumnSpan(help, 2);
        var buttons = new FlowLayoutPanel
        {
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            FlowDirection = FlowDirection.RightToLeft, WrapContents = false,
            Dock = DockStyle.Bottom, Padding = new Padding(20, 12, 20, 16),
            BackColor = Color.FromArgb(248, 250, 252), MinimumSize = new Size(0, 76)
        };
        var cancel = new Button { Text = "취소", DialogResult = DialogResult.Cancel, AutoSize = true, FlatStyle = FlatStyle.Flat, BackColor = Color.White, Padding = new Padding(14, 5, 14, 5) };
        cancel.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        var save = new Button { Text = "저장", AutoSize = true, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(37, 99, 235), ForeColor = Color.White, Padding = new Padding(14, 5, 14, 5) };
        save.FlatAppearance.BorderSize = 0;
        save.Click += (_, _) => SaveSchedule();
        buttons.Controls.AddRange([cancel, save]);
        Controls.Add(layout); Controls.Add(buttons); AcceptButton = save; CancelButton = cancel;
        _enabled.CheckedChanged += (_, _) => UpdateInputs();
        _type.SelectedIndexChanged += (_, _) => UpdateInputs();
        _weekdayEnabled.CheckedChanged += (_, _) => UpdateInputs();
        _weekendEnabled.CheckedChanged += (_, _) => UpdateInputs();
        _individual.CheckedChanged += (_, _) => UpdateInputs();
        UpdateInputs();
    }

    private void UpdateInputs()
    {
        _type.Enabled = _enabled.Checked;
        _start.Enabled = _end.Enabled = _enabled.Checked && _type.SelectedIndex == 0;
        _minutes.Enabled = _restart.Enabled = _enabled.Checked && _type.SelectedIndex == 1;
        foreach (var row in _typeRows) row.Label.Visible = row.Input.Visible = row.Type == _type.SelectedIndex;
        var weekly = _enabled.Checked && _type.SelectedIndex == 2;
        _individual.Enabled = weekly;
        _dailyPanel.Visible = _individual.Checked;
        foreach (var day in _days)
        {
            day.Enabled.Enabled = weekly;
            day.Start.Enabled = day.End.Enabled = weekly && day.Enabled.Checked;
        }
        _weekdayEnabled.Enabled = _weekendEnabled.Enabled = weekly && !_individual.Checked;
        _weekdayStart.Enabled = _weekdayEnd.Enabled = weekly && !_individual.Checked && _weekdayEnabled.Checked;
        _weekendStart.Enabled = _weekendEnd.Enabled = weekly && !_individual.Checked && _weekendEnabled.Checked;
        _walltimeHelp.Visible = _restartHelp.Visible = _type.SelectedIndex == 1;
        _weeklyHelp.Visible = _type.SelectedIndex == 2;
    }

    private void SaveSchedule()
    {
        var type = (DomainTimeType)_type.SelectedIndex;
        if (_enabled.Checked && type == DomainTimeType.Absolute && _end.Value <= _start.Value)
        {
            MessageBox.Show(this, "종료 시각은 시작 시각보다 늦어야 합니다.", "시간 확인");
            return;
        }
        var minutes = (int)_minutes.Value;
        var restart = _enabled.Checked && type == DomainTimeType.Walltime &&
            (_restart.Checked || !_original.Enabled || _original.Type != type || _original.WalltimeMinutes != minutes || _original.Countdown is null);
        Result = new DomainSchedule
        {
            Enabled = _enabled.Checked, Type = type,
            Start = new DateTimeOffset(_start.Value), End = new DateTimeOffset(_end.Value),
            WalltimeMinutes = minutes,
            Days = _individual.Checked ? _days.Select(d => new DailyBlockWindow
                { Enabled = d.Enabled.Checked, Start = d.Start.Value.TimeOfDay, End = d.End.Value.TimeOfDay }).ToArray() : null,
            Weekdays = new DailyBlockWindow { Enabled = _weekdayEnabled.Checked, Start = _weekdayStart.Value.TimeOfDay, End = _weekdayEnd.Value.TimeOfDay },
            Weekends = new DailyBlockWindow { Enabled = _weekendEnabled.Checked, Start = _weekendStart.Value.TimeOfDay, End = _weekendEnd.Value.TimeOfDay },
            WalltimeStartedAt = restart ? DateTimeOffset.UtcNow : _original.WalltimeStartedAt,
            Countdown = restart ? ElapsedCountdown.Start(minutes * 60000L) : _original.Countdown
        };
        DialogResult = DialogResult.OK;
        Close();
    }

    private Control HelpCard(string title, string body, Color background, Color accent)
    {
        var card = new TableLayoutPanel
        {
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Dock = DockStyle.Top,
            ColumnCount = 2, RowCount = 1, BackColor = background, Margin = new Padding(0, 0, 0, 8),
            Padding = new Padding(0, 12, 12, 12)
        };
        card.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 4));
        card.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        card.Controls.Add(new Panel { BackColor = accent, Dock = DockStyle.Fill, Margin = Padding.Empty }, 0, 0);
        var text = new FlowLayoutPanel
        {
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.TopDown, WrapContents = false, Margin = new Padding(12, 0, 0, 0)
        };
        text.Controls.Add(new Label { Text = title, AutoSize = true, ForeColor = accent, Font = new Font(Font, FontStyle.Bold), Margin = new Padding(0, 0, 0, 5) });
        var description = new Label { Text = body, AutoSize = true, ForeColor = Color.FromArgb(51, 65, 85), Margin = Padding.Empty };
        text.Controls.Add(description);
        text.SizeChanged += (_, _) => description.MaximumSize = new Size(Math.Max(1, text.ClientSize.Width), 0);
        card.Controls.Add(text, 1, 0);
        return card;
    }

    private static DateTimePicker DatePicker() => new() { Format = DateTimePickerFormat.Custom, CustomFormat = "yyyy-MM-dd HH:mm", Width = 250 };
    private static DateTimePicker TimePicker() => new() { Format = DateTimePickerFormat.Custom, CustomFormat = "HH:mm", ShowUpDown = true, Width = 95 };
    private static Control WindowInputs(CheckBox enabled, DateTimePicker start, DateTimePicker end, DailyBlockWindow window)
    {
        enabled.Checked = window.Enabled;
        start.Value = DateTime.Today.Add(window.Start);
        end.Value = DateTime.Today.Add(window.End);
        var panel = new FlowLayoutPanel { AutoSize = true, WrapContents = false, Margin = Padding.Empty };
        panel.Controls.AddRange([enabled, start, new Label { Text = "~", AutoSize = true, Margin = new Padding(3, 6, 3, 0) }, end]);
        return panel;
    }
    private void AddTypeRow(TableLayoutPanel panel, int row, string label, Control input, int type)
    {
        var caption = new Label { Text = label, AutoSize = true, Anchor = AnchorStyles.Left };
        panel.Controls.Add(caption, 0, row); panel.Controls.Add(input, 1, row);
        _typeRows.Add((caption, input, type));
    }
    private static void AddRow(TableLayoutPanel panel, int row, string label, Control input)
    {
        panel.Controls.Add(new Label { Text = label, AutoSize = true, Anchor = AnchorStyles.Left }, 0, row);
        panel.Controls.Add(input, 1, row);
    }
}
