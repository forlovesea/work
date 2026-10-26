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
            ControlStyles.OptimizedDoubleBuffer | ControlStyles.SupportsTransparentBackColor | ControlStyles.ResizeRedraw, true);
        BackColor = Color.Transparent;
        ForeColor = Color.FromArgb(71, 85, 105);
        AutoSize = true;
        Size = GetPreferredSize(Size.Empty);
        Margin = new Padding(10, 3, 4, 0);
        TabStop = false;
    }

    public override Size GetPreferredSize(Size proposedSize)
    {
        var scale = DeviceDpi / 96F;
        var caption = TextRenderer.MeasureText(Text, Font, Size.Empty, TextFormatFlags.NoPadding | TextFormatFlags.SingleLine);
        return new Size((int)Math.Ceiling(Math.Max(28 * scale, caption.Width + 4 * scale) + 26 * scale + 5 * scale),
            (int)Math.Ceiling(Math.Max(22 * scale, caption.Height + 4 * scale)));
    }

    private void UpdatePreferredSize() { if (AutoSize) Size = GetPreferredSize(Size.Empty); Invalidate(); }
    protected override void OnFontChanged(EventArgs e) { base.OnFontChanged(e); UpdatePreferredSize(); }
    protected override void OnTextChanged(EventArgs e) { base.OnTextChanged(e); UpdatePreferredSize(); }
    protected override void OnDpiChangedAfterParent(EventArgs e) { base.OnDpiChangedAfterParent(e); UpdatePreferredSize(); }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        var g = e.Graphics;
        var state = g.Save();
        var scale = DeviceDpi / 96F;
        var caption = TextRenderer.MeasureText(Text, Font, Size.Empty, TextFormatFlags.NoPadding | TextFormatFlags.SingleLine);
        var left = Math.Max(28 * scale, caption.Width + 4 * scale);
        // Keep the caption independent of the activity state.
        TextRenderer.DrawText(g, Text, Font,
            new Rectangle(0, 0, (int)(left - 3 * scale), ClientSize.Height), ForeColor,
            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        // Leave room for the centered pen and antialiasing inside the client area.
        var inset = Math.Max(2, 2 * scale);
        var width = Math.Min(26 * scale, ClientSize.Width - left - inset);
        var height = Math.Min(10 * scale, ClientSize.Height - 2 * inset);
        if (width <= 1 || height <= 1) { g.Restore(state); return; }
        var bounds = new RectangleF(left, (ClientSize.Height - height) / 2, width, height);
        var diameter = Math.Min(5 * scale, Math.Min(width, height));
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
