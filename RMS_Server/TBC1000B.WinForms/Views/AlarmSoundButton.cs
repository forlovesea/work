using System.Drawing.Drawing2D;

namespace TBC1000B.WinForms.Views;

internal sealed class AlarmSoundButton : Button
{
    private int _level;
    public int Level
    {
        get => _level;
        set
        {
            _level = Math.Clamp(value, 0, 3);
            AccessibleName = _level == 0 ? "알람 소리 꺼짐" : $"알람 소리 {_level}단계";
            AccessibleDescription = "클릭하면 알람 소리 단계를 변경합니다.";
            Invalidate();
        }
    }

    public AlarmSoundButton()
    {
        DoubleBuffered = true;
        FlatStyle = FlatStyle.Flat;
        BackColor = Color.FromArgb(239, 246, 255);
        FlatAppearance.BorderColor = Color.FromArgb(191, 219, 254);
        FlatAppearance.MouseOverBackColor = Color.FromArgb(219, 234, 254);
        FlatAppearance.MouseDownBackColor = Color.FromArgb(191, 219, 254);
        Cursor = Cursors.Hand;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        var g = e.Graphics;
        var state = g.Save();
        g.SmoothingMode = SmoothingMode.AntiAlias;
        var scale = Math.Min(ClientSize.Width / 48F, ClientSize.Height / 34F);
        g.TranslateTransform((ClientSize.Width - 48 * scale) / 2, (ClientSize.Height - 34 * scale) / 2);
        g.ScaleTransform(scale, scale);
        var color = !Enabled || Level == 0 ? Color.FromArgb(100, 116, 139) : Color.FromArgb(37, 99, 235);
        using var brush = new SolidBrush(color);
        g.FillPolygon(brush, new PointF[] { new(10, 13), new(16, 13), new(23, 7), new(23, 27), new(16, 21), new(10, 21) });
        using var pen = new Pen(color, 2.2F) { StartCap = LineCap.Round, EndCap = LineCap.Round };
        if (Level == 0)
        {
            g.DrawLine(pen, 29, 13, 37, 21);
            g.DrawLine(pen, 37, 13, 29, 21);
        }
        else
        {
            for (var wave = 0; wave < Level; wave++)
            {
                var radius = 8 + wave * 5;
                g.DrawArc(pen, 22 - radius, 17 - radius, radius * 2, radius * 2, -42, 84);
            }
        }
        g.Restore(state);
    }
}
