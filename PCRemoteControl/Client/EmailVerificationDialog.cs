namespace PCRemoteControl;

sealed class EmailVerificationDialog : Form
{
    readonly TextBox code = new() { MaxLength = 6, Width = 240 };
    readonly System.Windows.Forms.Timer timer = new() { Interval = 200 };
    public string Code => code.Text.Trim();

    public EmailVerificationDialog(CancellationToken token)
    {
        Text = "이메일 인증";
        ClientSize = new Size(460, 200);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition = FormStartPosition.CenterParent;
        MaximizeBox = MinimizeBox = false;
        var layout = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(20), FlowDirection = FlowDirection.TopDown, WrapContents = false };
        var label = new Label { AutoSize = true, Text = "forlovesea@gmail.com으로 인증코드를 보냈습니다.\n5분 안에 6자리 코드를 입력하세요." };
        var confirm = new Button { Text = "인증 후 연결", AutoSize = true, Enabled = false, DialogResult = DialogResult.OK };
        var cancel = new Button { Text = "취소", DialogResult = DialogResult.Cancel };
        var buttons = new FlowLayoutPanel { AutoSize = true };
        buttons.Controls.AddRange(new Control[] { confirm, cancel });
        layout.Controls.AddRange(new Control[] { label, code, buttons });
        Controls.Add(layout);
        AcceptButton = confirm;
        CancelButton = cancel;
        code.TextChanged += (_, _) => confirm.Enabled = Code.Length == 6 && Code.All(c => c >= '0' && c <= '9');
        timer.Tick += (_, _) => { if (token.IsCancellationRequested) { DialogResult = DialogResult.Cancel; Close(); } };
        Shown += (_, _) => { code.Focus(); timer.Start(); };
        FormClosed += (_, _) => timer.Stop();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) timer.Dispose();
        base.Dispose(disposing);
    }
}
