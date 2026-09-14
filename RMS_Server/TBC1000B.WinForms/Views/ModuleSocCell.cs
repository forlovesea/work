namespace TBC1000B.WinForms.Views;

internal static class ModuleSocCell
{
    public static void SetSoc(DataGridViewCell cell, int? value)
    {
        cell.Tag = value is >= 0 and <= 100 ? value : null;
        cell.ToolTipText = cell.Tag is int soc ? $"SOC 충전율: {soc}%" : "SOC 충전율: 데이터 없음";
        cell.DataGridView?.InvalidateCell(cell);
    }

    public static void Paint(object? sender, DataGridViewCellPaintingEventArgs e)
    {
        if (e.RowIndex < 0 || e.ColumnIndex != 0 || sender is not DataGridView grid || e.Graphics is null) return;
        var bounds = e.CellBounds;
        using var background = new SolidBrush(Color.FromArgb(241, 245, 249));
        using var fill = new SolidBrush(Color.FromArgb(110, 231, 183));
        e.Graphics.FillRectangle(background, bounds);
        if (grid[0, e.RowIndex].Tag is int soc)
            e.Graphics.FillRectangle(fill, bounds.X, bounds.Y, (int)Math.Round(bounds.Width * soc / 100d), bounds.Height);
        TextRenderer.DrawText(e.Graphics, Convert.ToString(e.FormattedValue), e.CellStyle?.Font ?? grid.Font,
            bounds, Color.FromArgb(30, 41, 59), TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix);
        e.Paint(e.ClipBounds, DataGridViewPaintParts.Border);
        if ((e.State & DataGridViewElementStates.Selected) != 0)
        {
            using var selection = new Pen(Color.FromArgb(37, 99, 235));
            e.Graphics.DrawRectangle(selection, bounds.X, bounds.Y, bounds.Width - 1, bounds.Height - 1);
        }
        e.Handled = true;
    }
}
