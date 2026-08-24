using TBC1000B.WinForms.Models;

namespace TBC1000B.WinForms.Views;

internal static class UiTheme
{
    public static readonly Color Header = Color.FromArgb(220, 234, 250);
    public static readonly Color Accent = Color.FromArgb(43, 137, 222);
    public static readonly Color Mint = Color.FromArgb(172, 239, 190);
    public static readonly Color Disabled = Color.FromArgb(176, 184, 192);
    public static readonly Color Critical = Color.FromArgb(239, 47, 51);
    public static readonly Color Major = Color.FromArgb(255, 126, 14);
    public static readonly Color Minor = Color.FromArgb(255, 211, 54);
    public static readonly Color Warning = Color.FromArgb(117, 199, 239);

    public static Color ForAlarm(AlarmLevel level) => level switch
    {
        AlarmLevel.Critical => Critical,
        AlarmLevel.Major => Major,
        AlarmLevel.Minor => Minor,
        AlarmLevel.Warning => Warning,
        _ => Mint
    };

    public static void ConfigureGrid(DataGridView grid)
    {
        grid.AllowUserToAddRows = false;
        grid.AllowUserToDeleteRows = false;
        grid.AllowUserToResizeRows = false;
        grid.RowHeadersVisible = false;
        grid.BackgroundColor = Color.White;
        grid.BorderStyle = BorderStyle.FixedSingle;
        grid.CellBorderStyle = DataGridViewCellBorderStyle.Single;
        grid.ColumnHeadersDefaultCellStyle.BackColor = Header;
        grid.ColumnHeadersDefaultCellStyle.ForeColor = Color.Black;
        grid.ColumnHeadersDefaultCellStyle.Font = new Font("맑은 고딕", 9F, FontStyle.Bold);
        grid.ColumnHeadersDefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleCenter;
        grid.DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleCenter;
        grid.DefaultCellStyle.Font = new Font("맑은 고딕", 9F);
        grid.EnableHeadersVisualStyles = false;
        grid.SelectionMode = DataGridViewSelectionMode.CellSelect;
    }

    public static Button Button(string text, Color? color = null)
    {
        var button = new Button { Text = text, AutoSize = false, Height = 27, FlatStyle = FlatStyle.Flat };
        button.FlatAppearance.BorderColor = color ?? Color.FromArgb(150, 150, 150);
        if (color is { } c) { button.BackColor = c; button.ForeColor = Color.White; }
        return button;
    }

    public static Control LegendChip(string text, Color background, Color foreground) => new RoundedLegendChip
    {
        Text = text, BackColor = background, ForeColor = foreground, Width = text == "Critical" ? 66 : 62,
        Height = 25, Margin = new Padding(3, 6, 3, 0), Font = new Font("맑은 고딕", 8F, FontStyle.Bold)
    };
}

internal sealed class RoundedLegendChip : Control
{
    public RoundedLegendChip() { SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint, true); }
    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        var rectangle = new Rectangle(0, 0, Width - 1, Height - 1); const int radius = 10;
        using var path = new System.Drawing.Drawing2D.GraphicsPath();
        path.AddArc(rectangle.Left, rectangle.Top, radius, radius, 180, 90); path.AddArc(rectangle.Right - radius, rectangle.Top, radius, radius, 270, 90);
        path.AddArc(rectangle.Right - radius, rectangle.Bottom - radius, radius, radius, 0, 90); path.AddArc(rectangle.Left, rectangle.Bottom - radius, radius, radius, 90, 90); path.CloseFigure();
        using var brush = new SolidBrush(BackColor); e.Graphics.FillPath(brush, path);
        using var pen = new Pen(ControlPaint.Dark(BackColor), 1F); e.Graphics.DrawPath(pen, path);
        TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle, ForeColor, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
    }
}
