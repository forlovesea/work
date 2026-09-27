namespace TBC1000B.WinForms.Views;

internal sealed class ModuleOrderRow : Label
{
    public int Position { get; init; }
    public string ModuleText { get; set; } = "미배치";
    public string Barcode { get; set; } = "-";

    public ModuleOrderRow()
    {
        DoubleBuffered = true;
        AutoSize = false;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.Clear(BackColor);
        var unit = DeviceDpi / 96F;
        var badgeWidth = (int)(104 * unit);
        var moduleWidth = (int)(82 * unit);
        var badge = new Rectangle(0, 0, badgeWidth, Height);
        var normal = BackColor.R > 230 && BackColor.G > 230 && BackColor.B > 230;
        using var brush = new SolidBrush(normal ? Color.FromArgb(226, 236, 249) : ControlPaint.Dark(BackColor, 0.05F));
        e.Graphics.FillRectangle(brush, badge);
        using var bold = new Font(Font, FontStyle.Bold);
        var flags = TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine | TextFormatFlags.EndEllipsis;
        TextRenderer.DrawText(e.Graphics, $"랙 {Position:00}번 위치", bold, badge,
            normal ? Color.FromArgb(30, 64, 110) : ForeColor, flags | TextFormatFlags.HorizontalCenter);
        TextRenderer.DrawText(e.Graphics, ModuleText, bold,
            new Rectangle(badgeWidth + (int)(8 * unit), 0, moduleWidth, Height), ForeColor, flags);
        var left = badgeWidth + moduleWidth + (int)(10 * unit);
        TextRenderer.DrawText(e.Graphics, Barcode, Font,
            new Rectangle(left, 0, Math.Max(0, Width - left - (int)(6 * unit)), Height), ForeColor, flags);
    }
}
