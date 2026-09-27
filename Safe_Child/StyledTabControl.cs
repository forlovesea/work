using System.Drawing.Drawing2D;

namespace SafeChild;

internal sealed class StyledTabControl : TabControl
{
    private const int WmPaint = 0x000F;

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
    public StyledTabControl()
    {
        Appearance = TabAppearance.Normal;
        DrawMode = TabDrawMode.OwnerDrawFixed;
        SizeMode = TabSizeMode.Fixed;
        SetStyle(ControlStyles.ResizeRedraw | ControlStyles.OptimizedDoubleBuffer, true);
        UpdateTabSize();
    }

    private void UpdateTabSize()
    {
        var scale = DeviceDpi / 96f;
        var width = (int)(152 * scale);
        using var selectedFont = new Font(Font, FontStyle.Bold);
        foreach (TabPage page in TabPages)
            width = Math.Max(width, TextRenderer.MeasureText(page.Text, selectedFont).Width + (int)(48 * scale));
        ItemSize = new Size(width, selectedFont.Height + (int)Math.Ceiling(28 * scale));
    }

    protected override void OnControlAdded(ControlEventArgs e) { base.OnControlAdded(e); UpdateTabSize(); }
    protected override void OnFontChanged(EventArgs e) { base.OnFontChanged(e); UpdateTabSize(); }
    protected override void OnDpiChangedAfterParent(EventArgs e) { base.OnDpiChangedAfterParent(e); UpdateTabSize(); }
    protected override void OnSelectedIndexChanged(EventArgs e) { base.OnSelectedIndexChanged(e); Invalidate(); }
    protected override bool ShowFocusCues => false;
    protected override void OnDrawItem(DrawItemEventArgs e)
    {
        if (e.Index < 0 || e.Index >= TabCount) return;
        DrawTab(e.Graphics, e.Index);
    }

    protected override void WndProc(ref Message m)
    {
        base.WndProc(ref m);
        if (m.Msg != WmPaint || TabCount == 0 || IsDisposed) return;
        using var graphics = CreateGraphics();
        DrawTabStrip(graphics);
    }

    private void DrawTabStrip(Graphics graphics)
    {
        var scale = DeviceDpi / 96f;
        var stripHeight = Math.Max(DisplayRectangle.Top, ItemSize.Height + (int)Math.Ceiling(8 * scale));
        using var backdrop = new SolidBrush(SystemColors.Control);
        graphics.FillRectangle(backdrop, new Rectangle(0, 0, Width, stripHeight));
        for (var i = 0; i < TabCount; i++)
            if (i != SelectedIndex) DrawTab(graphics, i);
        if (SelectedIndex >= 0 && SelectedIndex < TabCount) DrawTab(graphics, SelectedIndex);
    }

    private void DrawTab(Graphics graphics, int index)
    {
        var selected = index == SelectedIndex;
        var accent = _accents[index % _accents.Length];
        var tint = _tints[index % _tints.Length];
        var scale = DeviceDpi / 96f;
        var bounds = GetTabRect(index);
        using var backdrop = new SolidBrush(SystemColors.Control);
        graphics.FillRectangle(backdrop, Rectangle.Inflate(bounds, (int)Math.Ceiling(8 * scale), (int)Math.Ceiling(6 * scale)));
        var sideInset = selected ? (int)Math.Ceiling(4 * scale) : (int)Math.Ceiling(12 * scale);
        var card = new Rectangle(
            bounds.Left + sideInset,
            bounds.Top + (int)Math.Ceiling(9 * scale),
            Math.Max(1, bounds.Width - (sideInset * 2)),
            Math.Max(1, bounds.Height - (int)Math.Ceiling(13 * scale)));
        var radius = Math.Min(10 * scale, card.Height / 2f);
        using var shape = new GraphicsPath();
        var diameter = radius * 2;
        shape.AddArc(card.Left, card.Top, diameter, diameter, 180, 90);
        shape.AddArc(card.Right - diameter, card.Top, diameter, diameter, 270, 90);
        shape.AddArc(card.Right - diameter, card.Bottom - diameter, diameter, diameter, 0, 90);
        shape.AddArc(card.Left, card.Bottom - diameter, diameter, diameter, 90, 90);
        shape.CloseFigure();
        graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using var fill = new SolidBrush(selected ? accent : tint);
        graphics.FillPath(fill, shape);
        var textBounds = card;
        if (selected)
        {
            var arrowWidth = 11 * scale;
            var arrowHeight = 7 * scale;
            var centerX = card.Left + (card.Width / 2f);
            var top = bounds.Top + (1.5f * scale);
            PointF[] arrow =
            [
                new(centerX - (arrowWidth / 2f), top),
                new(centerX + (arrowWidth / 2f), top),
                new(centerX, top + arrowHeight)
            ];
            using var arrowBrush = new SolidBrush(accent);
            graphics.FillPolygon(arrowBrush, arrow);
        }
        using var font = new Font(Font, selected ? FontStyle.Bold : FontStyle.Regular);
        TextRenderer.DrawText(graphics, TabPages[index].Text, font, textBounds,
            selected ? Color.White : accent, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine | TextFormatFlags.NoPrefix);
    }
}
