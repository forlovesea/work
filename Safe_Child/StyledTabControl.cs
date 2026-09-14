using System.Drawing.Drawing2D;

namespace SafeChild;

internal sealed class StyledTabControl : TabControl
{
    private readonly Color[] _accents =
    [
        Color.FromArgb(30, 58, 138), Color.FromArgb(17, 94, 89),
        Color.FromArgb(76, 29, 149), Color.FromArgb(7, 89, 133), Color.FromArgb(146, 64, 14), Color.FromArgb(159, 51, 74)
    ];
    private readonly Color[] _tints =
    [
        Color.FromArgb(191, 219, 254), Color.FromArgb(153, 246, 228),
        Color.FromArgb(221, 214, 254), Color.FromArgb(186, 230, 253), Color.FromArgb(253, 230, 138), Color.FromArgb(254, 205, 211)
    ];
    private int _hovered = -1;

    public StyledTabControl()
    {
        DrawMode = TabDrawMode.OwnerDrawFixed;
        SizeMode = TabSizeMode.Fixed;
        UpdateTabSize();
    }

    private void UpdateTabSize()
    {
        var scale = DeviceDpi / 96f;
        var width = (int)(152 * scale);
        using var selectedFont = new Font(Font, FontStyle.Bold);
        foreach (TabPage page in TabPages)
            width = Math.Max(width, TextRenderer.MeasureText(page.Text, selectedFont).Width + (int)(48 * scale));
        ItemSize = new Size(width, selectedFont.Height + (int)Math.Ceiling(12 * scale));
    }

    protected override void OnControlAdded(ControlEventArgs e) { base.OnControlAdded(e); UpdateTabSize(); }
    protected override void OnFontChanged(EventArgs e) { base.OnFontChanged(e); UpdateTabSize(); }
    protected override void OnDpiChangedAfterParent(EventArgs e) { base.OnDpiChangedAfterParent(e); UpdateTabSize(); }
    protected override void OnSelectedIndexChanged(EventArgs e) { base.OnSelectedIndexChanged(e); Invalidate(); }
    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        var hovered = -1;
        for (var i = 0; i < TabCount; i++) if (GetTabRect(i).Contains(e.Location)) { hovered = i; break; }
        if (_hovered == hovered) return;
        _hovered = hovered; Invalidate();
    }
    protected override void OnMouseLeave(EventArgs e) { base.OnMouseLeave(e); _hovered = -1; Invalidate(); }

    protected override void OnDrawItem(DrawItemEventArgs e)
    {
        if (e.Index < 0 || e.Index >= TabCount) return;
        var selected = e.Index == SelectedIndex;
        var accent = _accents[e.Index % _accents.Length];
        var tint = _tints[e.Index % _tints.Length];
        var scale = DeviceDpi / 96f;
        var bounds = GetTabRect(e.Index);
        using var backdrop = new SolidBrush(SystemColors.Control);
        e.Graphics.FillRectangle(backdrop, bounds);
        var card = Rectangle.Inflate(bounds, -(int)(3 * scale), -(int)(3 * scale));
        var radius = Math.Min(10 * scale, card.Height / 2f);
        using var shape = new GraphicsPath();
        var diameter = radius * 2;
        shape.AddArc(card.Left, card.Top, diameter, diameter, 180, 90);
        shape.AddArc(card.Right - diameter, card.Top, diameter, diameter, 270, 90);
        shape.AddArc(card.Right - diameter, card.Bottom - diameter, diameter, diameter, 0, 90);
        shape.AddArc(card.Left, card.Bottom - diameter, diameter, diameter, 90, 90);
        shape.CloseFigure();
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using var fill = new SolidBrush(selected ? accent : tint);
        e.Graphics.FillPath(fill, shape);
        if (!selected && e.Index == _hovered)
        {
            using var border = new Pen(accent, 1.2f * scale);
            e.Graphics.DrawPath(border, shape);
        }
        using var font = new Font(Font, selected ? FontStyle.Bold : FontStyle.Regular);
        TextRenderer.DrawText(e.Graphics, TabPages[e.Index].Text, font, card,
            selected ? Color.White : accent, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine | TextFormatFlags.NoPrefix);
        if (selected && Focused && ShowFocusCues)
            ControlPaint.DrawFocusRectangle(e.Graphics, Rectangle.Inflate(card, -(int)(6 * scale), -(int)(6 * scale)), Color.White, accent);
    }
}
