using System.Drawing.Drawing2D;
using System.Windows.Forms;
using System.Drawing;

namespace PCRemoteControl;

internal static class PastelTheme
{
    public static readonly Color Ink = Color.FromArgb(58, 53, 73);
    public static readonly Color Lavender = Color.FromArgb(231, 222, 246);
    public static readonly Color Mint = Color.FromArgb(220, 239, 228);
    public static readonly Color Rose = Color.FromArgb(248, 226, 230);
    public static void Apply(Control root)
    {
        root.Font = new Font("맑은 고딕", 9.5f);
        root.ForeColor = Ink;
        root.BackColor = Color.FromArgb(248, 246, 251);
        StyleChildren(root);
    }
    static void StyleChildren(Control root)
    {
        foreach (Control c in root.Controls)
        {
            c.ForeColor = Ink;
            if (c is Button b)
            {
                b.Padding = new Padding(12, 5, 12, 5);
                b.Margin = new Padding(4);
                b.MinimumSize = new Size(100, 38);
                b.BackColor = b.Text.Contains("중지") || b.Text.Contains("종료") ? Rose :
                    b.Text.Contains("연결") || b.Text.Contains("시작") || b.Text == "원격접속" ? Mint : Lavender;
            }
            else if (c is TextBox t) { t.BorderStyle = BorderStyle.FixedSingle; t.BackColor = Color.White; }
            else if (c is ComboBox box) { box.FlatStyle = FlatStyle.Flat; box.BackColor = Color.White; }
            else if (c is NumericUpDown n) { n.BorderStyle = BorderStyle.FixedSingle; n.BackColor = Color.White; }
            else if (c is ListBox list)
            {
                list.BackColor = Color.FromArgb(255, 253, 249);
                list.BorderStyle = BorderStyle.None;
                list.DrawMode = DrawMode.OwnerDrawFixed;
                list.ItemHeight = 42;
                list.DrawItem += (_, e) => {
                    if (e.Index < 0) return;
                    bool selected = (e.State & DrawItemState.Selected) != 0;
                    using var brush = new SolidBrush(selected ? Lavender : list.BackColor);
                    e.Graphics.FillRectangle(brush, e.Bounds);
                    TextRenderer.DrawText(e.Graphics, list.GetItemText(list.Items[e.Index]), list.Font,
                        Rectangle.Inflate(e.Bounds, -12, 0), Ink, TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);
                    e.DrawFocusRectangle();
                };
            }
            else if (c is Label) { c.BackColor = Color.Transparent; c.Margin = new Padding(6, 9, 4, 4); }
            else if (c is Panel) c.BackColor = root.BackColor;
            StyleChildren(c);
        }
    }
}

internal sealed class PastelButton : Button
{
    bool hovered;
    public PastelButton()
    {
        FlatStyle = FlatStyle.Flat;
        FlatAppearance.BorderSize = 0;
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
    }
    protected override void OnMouseEnter(EventArgs e) { hovered = true; Invalidate(); base.OnMouseEnter(e); }
    protected override void OnMouseLeave(EventArgs e) { hovered = false; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.Clear(Parent?.BackColor ?? SystemColors.Control);
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        var rect = new Rectangle(1, 1, Width - 3, Height - 4);
        using var path = new GraphicsPath();
        const int diameter = 18;
        path.AddArc(rect.Left, rect.Top, diameter, diameter, 180, 90);
        path.AddArc(rect.Right - diameter, rect.Top, diameter, diameter, 270, 90);
        path.AddArc(rect.Right - diameter, rect.Bottom - diameter, diameter, diameter, 0, 90);
        path.AddArc(rect.Left, rect.Bottom - diameter, diameter, diameter, 90, 90);
        path.CloseFigure();
        using var shadow = new SolidBrush(Color.FromArgb(224, 219, 232));
        e.Graphics.TranslateTransform(0, 2);
        e.Graphics.FillPath(shadow, path);
        e.Graphics.ResetTransform();
        var fill = !Enabled ? Color.FromArgb(239, 237, 242) : hovered ? ControlPaint.Dark(BackColor, .04f) : BackColor;
        using var brush = new SolidBrush(fill);
        e.Graphics.FillPath(brush, path);
        using var pen = new Pen(Focused ? Color.FromArgb(133, 110, 168) : ControlPaint.Dark(fill, .05f), Focused ? 2 : 1);
        e.Graphics.DrawPath(pen, path);
        TextRenderer.DrawText(e.Graphics, Text, Font, rect, Enabled ? ForeColor : Color.FromArgb(137, 132, 146),
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
        if (Focused && ShowFocusCues) ControlPaint.DrawFocusRectangle(e.Graphics, Rectangle.Inflate(rect, -5, -5));
    }
}