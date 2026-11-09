using System.Drawing;
using System.Runtime.InteropServices;
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
                b.Padding = new Padding(12, 5, 12, 5);
                b.Margin = new Padding(4);
                b.MinimumSize = new Size(100, 36);
                b.FlatStyle = FlatStyle.Flat;
                b.FlatAppearance.BorderColor = Border;
                b.FlatAppearance.MouseOverBackColor = Color.FromArgb(55, 55, 55);
                b.FlatAppearance.MouseDownBackColor = Selection;
                b.UseVisualStyleBackColor = false;
                b.BackColor = b.Text is "서버 연결" or "원격접속" or "인증 후 연결" or "확인" or "감시 시작" ? Accent : Input;
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
    protected override void OnPaint(PaintEventArgs e)
    {
        var rect = new Rectangle(0, 0, Width - 1, Height - 1);
        Color fill = !Enabled ? DarkTheme.Surface : pressed ? DarkTheme.Selection : hovered ? ControlPaint.Light(BackColor, .12f) : BackColor;
        e.Graphics.Clear(fill);
        using var pen = new Pen(Focused ? DarkTheme.Accent : DarkTheme.Border);
        e.Graphics.DrawRectangle(pen, rect);
        TextRenderer.DrawText(e.Graphics, Text, Font, rect, Enabled ? ForeColor : DarkTheme.Muted,
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
        if (Focused && ShowFocusCues) ControlPaint.DrawFocusRectangle(e.Graphics, Rectangle.Inflate(rect, -4, -4), DarkTheme.Ink, fill);
    }
}
