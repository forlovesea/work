using System.Drawing.Drawing2D;

namespace SafeChild;

internal sealed class ChildMessagePopup : Form
{
    private readonly Label _site = new() { AutoSize = false, Dock = DockStyle.Top, Height = 38, TextAlign = ContentAlignment.MiddleCenter, ForeColor = Color.FromArgb(148, 99, 67), AutoEllipsis = true, UseMnemonic = false };
    private readonly Label _message = new() { AutoSize = false, UseMnemonic = false, ForeColor = Color.FromArgb(71, 57, 49) };

    public ChildMessagePopup(string domain, string message)
    {
        Text = "보호자가 전하는 메시지";
        Font = new Font("맑은 고딕", 11F);
        BackColor = Color.FromArgb(255, 249, 241);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; MinimizeBox = false; TopMost = true;
        ClientSize = new Size(580, Math.Min(550, Math.Max(360, Screen.PrimaryScreen!.WorkingArea.Height - 100)));
        Padding = new Padding(28, 18, 28, 18);
        var header = new Panel { Dock = DockStyle.Top, Height = 150 };
        var symbol = new Panel { Dock = DockStyle.Top, Height = 72 };
        symbol.Paint += (_, e) =>
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            var cx = symbol.Width / 2f;
            using var circle = new SolidBrush(Color.FromArgb(255, 229, 214));
            e.Graphics.FillEllipse(circle, cx - 30, 4, 60, 60);
            using var heart = new GraphicsPath();
            heart.AddBezier(cx, 48, cx - 35, 28, cx - 10, 12, cx, 27);
            heart.AddBezier(cx, 27, cx + 10, 12, cx + 35, 28, cx, 48);
            using var fill = new SolidBrush(Color.FromArgb(213, 117, 96));
            e.Graphics.FillPath(fill, heart);
        };
        var title = new Label { Text = "잠깐, 전하고 싶은 말이 있어요", Dock = DockStyle.Top, Height = 40, TextAlign = ContentAlignment.MiddleCenter, Font = new Font(Font.FontFamily, 17, FontStyle.Bold), ForeColor = Color.FromArgb(116, 70, 52) };
        header.Controls.Add(_site); header.Controls.Add(title); header.Controls.Add(symbol);
        var footer = new Panel { Dock = DockStyle.Bottom, Height = 76 };
        var close = new Button { Text = "알겠어요", Size = new Size(150, 44), FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(85, 119, 101), ForeColor = Color.White, Cursor = Cursors.Hand, Font = new Font(Font, FontStyle.Bold) };
        close.FlatAppearance.BorderSize = 0;
        close.Click += (_, _) => Close();
        footer.Controls.Add(close);
        footer.Resize += (_, _) => close.Location = new Point((footer.ClientSize.Width - close.Width) / 2, 20);
        var body = new Panel { Dock = DockStyle.Fill, AutoScroll = true, BackColor = Color.FromArgb(255, 253, 249), Padding = new Padding(20), AutoScrollMargin = new Size(0, 16) };
        _message.Font = new Font(Font.FontFamily, 12F);
        body.Controls.Add(_message);
        void FitText()
        {
            var width = Math.Max(100, body.ClientSize.Width - body.Padding.Horizontal - SystemInformation.VerticalScrollBarWidth);
            var height = TextRenderer.MeasureText(_message.Text, _message.Font, new Size(width, int.MaxValue), TextFormatFlags.WordBreak | TextFormatFlags.TextBoxControl | TextFormatFlags.NoPrefix).Height + 12;
            _message.SetBounds(20, 20, width, height);
        }
        body.ClientSizeChanged += (_, _) => FitText();
        _message.TextChanged += (_, _) => FitText();
        Controls.Add(body); Controls.Add(footer); Controls.Add(header);
        AcceptButton = close; CancelButton = close;
        Display(domain, message);
    }

    public void Display(string domain, string message)
    {
        _site.Text = domain;
        _message.Text = message;
    }
}
