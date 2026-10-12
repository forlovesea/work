using System.Drawing.Drawing2D;

namespace TBC1000B.WinForms.Views;

internal sealed class TrafficLed : Control
{
    private bool _isActive;
    public Color ActiveColor { get; init; } = Color.SeaGreen;
    public bool IsActive
    {
        get => _isActive;
        set
        {
            if (_isActive == value) return;
            _isActive = value;
            Invalidate();
        }
    }

    public TrafficLed()
    {
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
            ControlStyles.OptimizedDoubleBuffer | ControlStyles.SupportsTransparentBackColor, true);
        BackColor = Color.Transparent;
        ForeColor = Color.FromArgb(71, 85, 105);
        Size = new Size(57, 22);
        Margin = new Padding(10, 3, 0, 0);
        TabStop = false;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        var g = e.Graphics;
        var state = g.Save();
        var scale = DeviceDpi / 96F;
        // Keep the caption independent of the activity state.
        TextRenderer.DrawText(g, Text, Font,
            new Rectangle(0, 0, (int)(25 * scale), ClientSize.Height), ForeColor,
            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        var bounds = new RectangleF(28 * scale, (ClientSize.Height - 10 * scale) / 2, 26 * scale, 10 * scale);
        var diameter = 5 * scale;
        using var shape = new GraphicsPath();
        shape.AddArc(bounds.Left, bounds.Top, diameter, diameter, 180, 90);
        shape.AddArc(bounds.Right - diameter, bounds.Top, diameter, diameter, 270, 90);
        shape.AddArc(bounds.Right - diameter, bounds.Bottom - diameter, diameter, diameter, 0, 90);
        shape.AddArc(bounds.Left, bounds.Bottom - diameter, diameter, diameter, 90, 90);
        shape.CloseFigure();
        var fill = IsActive ? ActiveColor : Color.FromArgb(226, 232, 240);
        using var brush = new SolidBrush(fill);
        using var border = new Pen(IsActive ? ControlPaint.Dark(ActiveColor) : Color.FromArgb(148, 163, 184), scale);
        g.FillPath(brush, shape);
        g.DrawPath(border, shape);
        g.Restore(state);
    }
}
