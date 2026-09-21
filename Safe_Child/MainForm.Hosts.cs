namespace SafeChild;

public sealed partial class MainForm
{
    private HostsStatus? _hostsStatus;
    private long _lastHostsCheck = long.MinValue;
    private readonly Label _hostsCheckLabel = new() { AutoSize = true, Padding = new Padding(8), ForeColor = Color.DimGray };

    private void RefreshHostsStatus(bool force = false)
    {
        var ticks = Environment.TickCount64;
        if (!force && _hostsStatus is not null && ticks - _lastHostsCheck < 5000) return;
        _lastHostsCheck = ticks;
        _hostsStatus = HostsStatus.Read();
        _hostsCheckLabel.Text = $"hosts 확인: {_hostsStatus.CheckedAt:HH:mm:ss} · " +
            (_hostsStatus.Error is null ? "5초마다 자동 확인 · 상세 주소는 상태 셀에 마우스를 올려 확인" : "파일 읽기 실패");
        _hostsCheckLabel.ForeColor = _hostsStatus.Error is null ? Color.DimGray : Color.Firebrick;
        _domainGrid.InvalidateColumn(_domainGrid.Columns["HostsActualState"]!.Index);
    }

    private void FormatHostsStatus(object? sender, DataGridViewCellFormattingEventArgs e)
    {
        if (e.RowIndex < 0 || e.ColumnIndex < 0 || _domainGrid.Columns[e.ColumnIndex].Name != "HostsActualState" ||
            _domainGrid.Rows[e.RowIndex].DataBoundItem is not BlockEntry entry) return;
        var now = DateTimeOffset.UtcNow;
        var expected = !_store.Settings.IsAllowAllActive(now) && entry.ShouldBlock(now);
        var status = _hostsStatus?.Describe(entry.Domain, expected);
        e.Value = status?.Text ?? "확인 전";
        if (e.CellStyle is not null)
        {
            var (background, foreground) = status switch
            {
                null => (Color.FromArgb(241, 245, 249), Color.FromArgb(71, 85, 105)),
                { Matches: false } => (Color.FromArgb(254, 243, 199), Color.FromArgb(146, 64, 14)),
                { Text: "차단" } => (Color.FromArgb(254, 226, 226), Color.FromArgb(153, 27, 27)),
                _ => (Color.FromArgb(220, 252, 231), Color.FromArgb(22, 101, 52))
            };
            e.CellStyle.BackColor = background;
            e.CellStyle.ForeColor = foreground;
            // Keep the status color readable when its row is selected.
            e.CellStyle.SelectionBackColor = ControlPaint.Dark(background, 0.05f);
            e.CellStyle.SelectionForeColor = foreground;
        }
        _domainGrid.Rows[e.RowIndex].Cells[e.ColumnIndex].ToolTipText = status?.Detail ?? "hosts 파일 확인 대기 중";
        e.FormattingApplied = true;
    }
}
