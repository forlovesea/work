namespace PCRemoteControl;

sealed class FullscreenHintDialog : Form
{
    readonly System.Windows.Forms.Timer autoClose = new() { Interval = 3000 };
    public bool ExitFullscreen { get; private set; }

    public FullscreenHintDialog()
    {
        Text = "전체화면 안내";
        ClientSize = new Size(460, 155);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition = FormStartPosition.CenterParent;
        MaximizeBox = MinimizeBox = false;
        ShowInTaskbar = false;
        KeyPreview = true;
        var message = new Label
        {
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
            Text = "Esc 또는 F11을 누르면 원래 화면으로 돌아갑니다.\n\n이 안내는 3초 뒤 자동으로 닫힙니다."
        };
        var confirm = new AppButton { Text = "확인", AutoSize = true, DialogResult = DialogResult.OK };
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 55, FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(8) };
        buttons.Controls.Add(confirm);
        Controls.Add(message);
        Controls.Add(buttons);
        DarkTheme.Apply(this);
        AcceptButton = confirm;
        autoClose.Tick += (_, _) => Close();
        Shown += (_, _) => autoClose.Start();
        FormClosed += (_, _) => autoClose.Stop();
        KeyDown += (_, e) =>
        {
            if (e.KeyCode is Keys.Escape or Keys.F11)
            {
                e.SuppressKeyPress = true;
                ExitFullscreen = true;
                Close();
            }
        };
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) autoClose.Dispose();
        base.Dispose(disposing);
    }
}
