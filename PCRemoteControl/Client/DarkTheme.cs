using System.Drawing;
using System.Runtime.InteropServices;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace PCRemoteControl;

internal static class DarkTheme
{
    public static readonly Color Ink = Color.FromArgb(204, 204, 204);
    public static readonly Color Background = Color.FromArgb(24, 24, 24);
    public static readonly Color Editor = Color.FromArgb(17, 18, 19);
    public static readonly Color Surface = Color.FromArgb(32, 32, 32);
    public static readonly Color Input = Color.FromArgb(43, 43, 43);
    public static readonly Color Border = Color.FromArgb(60, 60, 60);
    public static readonly Color Accent = Color.FromArgb(0, 120, 212);
    public static readonly Color Selection = Color.FromArgb(4, 57, 94);
    public static readonly Color Muted = Color.FromArgb(145, 145, 145);

    [DllImport("dwmapi.dll")]
    static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

    public static void Apply(Control root)
    {
        root.Font = new Font("Segoe UI", 10f);
        root.ForeColor = Ink;
        root.BackColor = Background;
        StyleChildren(root);
        if (root is Form form)
        {
            void TitleBar(object? sender, EventArgs e)
            {
                int dark = 1;
                if (DwmSetWindowAttribute(form.Handle, 20, ref dark, sizeof(int)) != 0)
                    DwmSetWindowAttribute(form.Handle, 19, ref dark, sizeof(int));
            }
            form.HandleCreated += TitleBar;
            if (form.IsHandleCreated) TitleBar(form, EventArgs.Empty);
        }
    }

    static void StyleChildren(Control root)
    {
        foreach (Control c in root.Controls)
        {
            c.ForeColor = Ink;
            if (c is Button b)
            {
                b.Padding = new Padding(10, 2, 10, 2);
                b.Margin = new Padding(3);
                b.MinimumSize = new Size(76, 30);
                b.Font = new Font(root.Font.FontFamily, 9f, FontStyle.Regular);
                b.FlatStyle = FlatStyle.Flat;
                b.FlatAppearance.BorderColor = Border;
                b.FlatAppearance.MouseOverBackColor = Color.FromArgb(55, 55, 55);
                b.FlatAppearance.MouseDownBackColor = Selection;
                b.UseVisualStyleBackColor = false;
                b.BackColor = b.Text is "서버 연결" or "원격접속" or "인증 후 연결" or "확인" or "감시 시작" ? Accent : Color.FromArgb(36, 36, 36);
                if (b.BackColor == Accent) b.ForeColor = Color.White;
            }
            else if (c is TextBox t) { t.BorderStyle = BorderStyle.FixedSingle; t.BackColor = Input; }
            else if (c is ComboBox box) { box.FlatStyle = FlatStyle.Flat; box.BackColor = Input; }
            else if (c is NumericUpDown n) { n.BorderStyle = BorderStyle.FixedSingle; n.BackColor = Input; }
            else if (c is ListBox list)
            {
                list.BackColor = Background;
                list.BorderStyle = BorderStyle.None;
                list.DrawMode = DrawMode.OwnerDrawFixed;
                list.ItemHeight = 36;
                list.DrawItem += (_, e) => {
                    if (e.Index < 0) return;
                    bool selected = (e.State & DrawItemState.Selected) != 0;
                    using var brush = new SolidBrush(selected ? Selection : list.BackColor);
                    e.Graphics.FillRectangle(brush, e.Bounds);
                    TextRenderer.DrawText(e.Graphics, list.GetItemText(list.Items[e.Index]), list.Font,
                        Rectangle.Inflate(e.Bounds, -10, 0), Ink, TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);
                    e.DrawFocusRectangle();
                };
            }
            else if (c is Label) { c.BackColor = Color.Transparent; c.Margin = new Padding(6, 8, 4, 4); }
            else if (c is Panel) c.BackColor = root.BackColor;
            StyleChildren(c);
        }
    }
}

internal sealed class AppButton : Button
{
    bool hovered, pressed;
    public AppButton()
    {
        FlatStyle = FlatStyle.Flat;
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
    }
    protected override void OnMouseEnter(EventArgs e) { hovered = true; Invalidate(); base.OnMouseEnter(e); }
    protected override void OnMouseLeave(EventArgs e) { hovered = pressed = false; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnMouseDown(MouseEventArgs e) { pressed = e.Button == MouseButtons.Left; Invalidate(); base.OnMouseDown(e); }
    protected override void OnMouseUp(MouseEventArgs e) { pressed = false; Invalidate(); base.OnMouseUp(e); }
    protected override void OnMouseCaptureChanged(EventArgs e) { pressed = false; Invalidate(); base.OnMouseCaptureChanged(e); }
    protected override void OnKeyDown(KeyEventArgs e) { if (e.KeyCode == Keys.Space) { pressed = true; Invalidate(); } base.OnKeyDown(e); }
    protected override void OnKeyUp(KeyEventArgs e) { if (e.KeyCode == Keys.Space) { pressed = false; Invalidate(); } base.OnKeyUp(e); }
    protected override void OnLostFocus(EventArgs e) { pressed = false; Invalidate(); base.OnLostFocus(e); }
    public override Size GetPreferredSize(Size proposedSize)
    {
        var text = TextRenderer.MeasureText(Text, Font, Size.Empty, TextFormatFlags.SingleLine);
        return new Size(Math.Max(MinimumSize.Width, text.Width + Padding.Horizontal + 4),
            Math.Max(MinimumSize.Height, text.Height + Padding.Vertical + 4));
    }
    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.Clear(Parent?.BackColor ?? DarkTheme.Background);
        if (Width < 4 || Height < 4) return;
        float scale = DeviceDpi / 96f;
        var rect = new Rectangle(1, 1, Width - 3, Height - 3);
        bool primary = BackColor == DarkTheme.Accent;
        Color fill = !Enabled ? Color.FromArgb(29, 29, 29)
            : pressed ? (primary ? Color.FromArgb(0, 92, 165) : Color.FromArgb(30, 30, 30))
            : hovered ? (primary ? Color.FromArgb(20, 132, 220) : Color.FromArgb(45, 45, 45)) : BackColor;
        bool focus = Focused && ShowFocusCues;
        Color outline = focus ? Color.FromArgb(117, 190, 255) : primary ? fill
            : hovered && Enabled ? Color.FromArgb(80, 80, 80) : Color.FromArgb(54, 54, 54);
        float diameter = Math.Min(10 * scale, Math.Min(rect.Width, rect.Height));
        using var path = new GraphicsPath();
        path.AddArc(rect.Left, rect.Top, diameter, diameter, 180, 90);
        path.AddArc(rect.Right - diameter, rect.Top, diameter, diameter, 270, 90);
        path.AddArc(rect.Right - diameter, rect.Bottom - diameter, diameter, diameter, 0, 90);
        path.AddArc(rect.Left, rect.Bottom - diameter, diameter, diameter, 90, 90);
        path.CloseFigure();
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using var brush = new SolidBrush(fill);
        using var pen = new Pen(outline, (focus ? 1.5f : 1f) * scale);
        e.Graphics.FillPath(brush, path);
        e.Graphics.DrawPath(pen, path);
        if (pressed) rect.Offset(0, 1);
        TextRenderer.DrawText(e.Graphics, Text, Font, rect, Enabled ? ForeColor : DarkTheme.Muted,
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine | TextFormatFlags.EndEllipsis);
    }
}
