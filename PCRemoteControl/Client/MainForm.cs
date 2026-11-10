using System.Text.Json;

namespace PCRemoteControl;
sealed class RemoteView : PictureBox
{
    string message = "HOST에서 TARGET을 선택한 뒤 원격접속을 누르세요.";
    public string Message { get => message; set { message = value; Invalidate(); } }
    public RemoteView() { SetStyle(ControlStyles.Selectable, true); TabStop = true; }
    protected override bool IsInputKey(Keys keyData) => true;
    protected override void OnPaint(PaintEventArgs pe)
    {
        base.OnPaint(pe);
        if (Image == null)
            TextRenderer.DrawText(pe.Graphics, message, Font, Rectangle.Inflate(ClientRectangle, -24, -24),
                DarkTheme.Ink, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.WordBreak);
    }
}
sealed class MainForm : Form
{
    readonly TextBox server = new() { Width = 190, Text = "61.105.141.21", PlaceholderText = "relay.example.com" };
    readonly NumericUpDown port = new() { Minimum = 1, Maximum = 65535, Value = 61000, Width = 75 };
    readonly TextBox password = new() { Text = "jjh1234", UseSystemPasswordChar = true, Width = 100 };
    readonly Button passwordEye = new() { AccessibleName = "비밀번호 표시", FlatStyle = FlatStyle.Flat };
    readonly ToolTip passwordTip = new();
    readonly TextBox targetName = new() { Text = Environment.MachineName, Width = 150, MaxLength = 80 };
    readonly ComboBox role = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 100 };
    readonly AppButton start = new() { Text = "서버 연결", AutoSize = true };
    readonly AppButton stop = new() { Text = "연결 중지", AutoSize = true, Enabled = false };
    readonly AppButton refresh = new() { Text = "목록 새로고침", AutoSize = true };
    readonly AppButton connect = new() { Text = "원격접속", AutoSize = true };
    readonly AppButton disconnect = new() { Text = "원격접속 종료", AutoSize = true };
    readonly AppButton full = new() { Text = "전체 화면 (F11)", AutoSize = true };
    readonly Label status = new() { Dock = DockStyle.Bottom, Height = 32, Text = "서버 주소를 입력하세요.", Padding = new Padding(8) };
    readonly ListBox targets = new() { Dock = DockStyle.Fill, DisplayMember = "Label" };
    readonly Panel side = new() { Dock = DockStyle.Left, Width = 250 };
    readonly FlowLayoutPanel settings = new() { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(10) };
    readonly RemoteView view = new() { Dock = DockStyle.Fill, BackColor = Color.FromArgb(25, 28, 34), SizeMode = PictureBoxSizeMode.Zoom };
    readonly System.Windows.Forms.Timer heartbeat = new() { Interval = 10000 };
    readonly System.Windows.Forms.Timer capture = new() { Interval = 125 };
    readonly System.Windows.Forms.Timer listing = new() { Interval = 5000 };
    readonly string settingsFile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PCRemoteControl", "settings.json");
    string id = Guid.NewGuid().ToString("N");
    CancellationTokenSource? lifetime;
    Connection? connection;
    bool paired, sendingFrame, fullScreen, running, targetMode;
    Rectangle oldBounds;
    FormWindowState oldState;
    long lastMove;
    long lastFrameAt, pairedAt, receivedFrames, sentFrames, nextCaptureAt;
    int sessionGeneration;
    string? captureError;
    readonly System.Windows.Forms.Timer health = new() { Interval = 2000 };
    readonly string? watchdogFolder;
    readonly bool fixedTarget;
    void WriteHealth(string state)
    {
        if (watchdogFolder == null) return;
        try { File.WriteAllText(Path.Combine(watchdogFolder, "health"), state); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
    record Target(string Id, string Name, string State) { public string Label => $"{Name} [{(State == "busy" ? "사용 중" : "연결 가능")}]"; }

    public MainForm(bool target, bool autoConnect = false, string? watchdogFolder = null)
    {
        this.watchdogFolder = watchdogFolder;
        fixedTarget = target;
        Text = "PCRemoteControl v0.1.3 · Windows HOST / TARGET";
        Size = new Size(1180, 780); MinimumSize = new Size(800, 500); KeyPreview = true;
        role.Items.AddRange(new object[] { "HOST", "TARGET" }); role.SelectedIndex = target ? 1 : 0;
        LoadSettings();
        if (target)
        {
            try { password.Text = TargetRecovery.Load() ?? password.Text; }
            catch (Exception) { autoConnect = false; status.Text = "저장 비밀번호 복구 실패 · 비밀번호를 다시 입력하세요."; }
        }
        health.Tick += (_, _) => { WriteHealth(running ? "running" : "paused"); CheckFrameHealth(); };
        WriteHealth("paused"); health.Start();
        Shown += async (_, _) => { if (target && autoConnect) await Start(); };
        var passwordGroup = new FlowLayoutPanel { AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, WrapContents = false, Margin = Padding.Empty };
        passwordGroup.Controls.AddRange(new Control[] { password, passwordEye });
        settings.Controls.AddRange(new Control[] { new Label { Text = "Relay 주소", AutoSize = true }, server, port, role, new Label { Text = "비밀번호", AutoSize = true }, passwordGroup, new Label { Text = "TARGET 이름", AutoSize = true }, targetName, start, stop });
        var actions = new FlowLayoutPanel { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(10) };
        actions.Controls.AddRange(new Control[] { refresh, connect, disconnect, full });
        actions.FlowDirection = FlowDirection.TopDown; actions.WrapContents = false;
        side.Padding = new Padding(10);
        side.Controls.Add(targets); side.Controls.Add(actions);
        Controls.Add(view); Controls.Add(side); Controls.Add(settings); Controls.Add(status);
        DarkTheme.Apply(this);
        passwordEye.MinimumSize = Size.Empty;
        passwordEye.Size = new Size(34, password.PreferredHeight);
        passwordEye.Padding = Padding.Empty;
        passwordEye.Margin = new Padding(0, password.Margin.Top, 3, 3);
        passwordTip.SetToolTip(passwordEye, "비밀번호 표시");
        passwordEye.Click += (_, _) =>
        {
            password.UseSystemPasswordChar = !password.UseSystemPasswordChar;
            string action = password.UseSystemPasswordChar ? "비밀번호 표시" : "비밀번호 숨기기";
            passwordEye.AccessibleName = action;
            passwordTip.SetToolTip(passwordEye, action);
            passwordEye.Invalidate();
        };
        passwordEye.Paint += (_, e) =>
        {
            e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            float x = passwordEye.ClientSize.Width / 2f, y = passwordEye.ClientSize.Height / 2f;
            using var pen = new Pen(passwordEye.Enabled ? DarkTheme.Ink : SystemColors.GrayText, 1.6f);
            e.Graphics.DrawBezier(pen, x - 10, y, x - 4, y - 9, x + 4, y - 9, x + 10, y);
            e.Graphics.DrawBezier(pen, x - 10, y, x - 4, y + 9, x + 4, y + 9, x + 10, y);
            e.Graphics.DrawEllipse(pen, x - 3, y - 3, 6, 6);
            if (password.UseSystemPasswordChar) e.Graphics.DrawLine(pen, x - 10, y + 8, x + 10, y - 8);
        };
        status.Height = 46; status.BackColor = DarkTheme.Surface;
        view.BackColor = DarkTheme.Editor;
        foreach (Control action in actions.Controls) action.Width = 205;
        start.Click += async (_, _) => await Start();
        stop.Click += (_, _) => Stop();
        refresh.Click += async (_, _) => await Send(new { type = "list" });
        connect.Click += async (_, _) => { if (targets.SelectedItem is Target t) await Send(new { type = "connect", id = t.Id }); };
        disconnect.Click += async (_, _) => await Send(new { type = "disconnect" });
        full.Click += (_, _) => ToggleFull();
        heartbeat.Tick += async (_, _) => await Send(new { type = "ping" });
        listing.Tick += async (_, _) => { if (!targetMode && connection != null) await Send(new { type = "list" }); };
        capture.Tick += async (_, _) => await CaptureFrame();
        view.MouseDown += async (_, e) => { view.Focus(); view.Capture = true; await Mouse(e, true); };
        view.MouseUp += async (_, e) => { await Mouse(e, false); view.Capture = false; };
        view.MouseMove += async (_, e) => { if (Environment.TickCount64 - lastMove > 35) { lastMove = Environment.TickCount64; await Mouse(e, null); } };
        view.MouseWheel += async (_, e) => await Mouse(e, null, e.Delta);
        KeyDown += async (_, e) =>
        {
            if (e.KeyCode == Keys.F11) { ToggleFull(); e.SuppressKeyPress = true; return; }
            if (e.KeyCode == Keys.Escape && fullScreen) { ToggleFull(); e.SuppressKeyPress = true; return; }
            if (CanInput) { e.SuppressKeyPress = true; await Send(new { type = "input", action = "key", key = (int)e.KeyCode, down = true }); }
        };
        KeyUp += async (_, e) => { if (CanInput && e.KeyCode != Keys.F11) { e.SuppressKeyPress = true; await Send(new { type = "input", action = "key", key = (int)e.KeyCode, down = false }); } };
        view.LostFocus += async (_, _) => { if (paired && !targetMode) await Send(new { type = "input", action = "release" }); };
        Deactivate += async (_, _) => { if (paired && !targetMode) await Send(new { type = "input", action = "release" }); };
        FormClosing += (_, _) => { health.Stop(); Stop(); WriteHealth("stopped"); };
        FormClosed += (_, _) => { passwordTip.Dispose(); health.Dispose(); heartbeat.Dispose(); capture.Dispose(); listing.Dispose(); view.Image?.Dispose(); };
        role.SelectedIndexChanged += (_, _) => UpdateControls();
        UpdateControls();
    }
    bool CanInput => paired && !targetMode && view.Focused && view.Image != null;
    void UpdateControls()
    {
        bool isTarget = role.SelectedIndex == 1;
        refresh.Enabled = connect.Enabled = !isTarget && connection != null && !paired;
        disconnect.Enabled = paired; full.Enabled = !isTarget;
        targetName.Enabled = isTarget && !running;
        role.Enabled = server.Enabled = port.Enabled = password.Enabled = !running;
        if (fixedTarget) role.Enabled = false;
        start.Enabled = !running; stop.Enabled = running;
    }
    void LoadSettings()
    {
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(settingsFile));
            var s = doc.RootElement;
            server.Text = s.GetProperty("server").GetString(); port.Value = s.GetProperty("port").GetInt32();
            id = s.GetProperty("id").GetString()!; targetName.Text = s.GetProperty("name").GetString();
        }
        catch (Exception ex) when (ex is IOException or JsonException or ArgumentException or KeyNotFoundException) { }
    }
    async Task Start()
    {
        if (running) return;
        if (string.IsNullOrWhiteSpace(server.Text) || string.IsNullOrWhiteSpace(password.Text) || string.IsNullOrWhiteSpace(targetName.Text)) { status.Text = "서버 주소, 비밀번호, TARGET 이름을 확인하세요."; return; }
        if (port.Value >= 55000 && port.Value <= 60000) { status.Text = "55000~60000은 기존 스마트폰용 예약 포트입니다. 기본 61000을 사용하세요."; return; }
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(settingsFile)!);
            File.WriteAllText(settingsFile, JsonSerializer.Serialize(new { server = server.Text.Trim(), port = (int)port.Value, id, name = targetName.Text }));
            if (role.SelectedIndex == 1) TargetRecovery.Save(password.Text);
        }
        catch (Exception ex) { status.Text = "설정 저장 실패: " + ex.Message; return; }
        lifetime = new(); var token = lifetime.Token; running = true; targetMode = role.SelectedIndex == 1; UpdateControls();
        WriteHealth("running");
        do
        {
            using var c = new Connection();
            try
            {
                status.Text = "Relay 서버 연결 중…";
                await c.Open(server.Text.Trim(), (int)port.Value, new { type = "hello", role = targetMode ? "target" : "host", password = password.Text, id, name = targetName.Text }, RequestEmailCode, token);
                connection = c; heartbeat.Start(); listing.Start(); capture.Start(); UpdateControls();
                status.Text = targetMode ? "TARGET 연결 유지 중 · HOST 접속 시 화면과 키보드/마우스 제어가 허용됩니다." : "인증 완료 · TARGET을 선택하고 원격접속을 누르세요.";
                if (!targetMode) await c.Send(new { type = "list" }, token);
                while (!token.IsCancellationRequested) HandleMessage(await c.Read(token));
            }
            catch (LoginException ex) { lifetime.Cancel(); WriteHealth("paused"); status.Text = ex.Message; }
            catch (Exception ex) { if (!token.IsCancellationRequested) { DiagnosticLog.Write("connection", ex.GetType().Name + ": " + ex.Message); status.Text = "연결 종료: " + ex.Message + (targetMode ? " · 5초 후 재연결" : ""); } }
            finally { connection = null; heartbeat.Stop(); listing.Stop(); capture.Stop(); EndSession(); UpdateControls(); }
            if (!targetMode || token.IsCancellationRequested) break;
            try { await Task.Delay(5000, token); } catch (OperationCanceledException) { break; }
        } while (!token.IsCancellationRequested);
        running = false; UpdateControls();
    }
    string? RequestEmailCode(CancellationToken token)
    {
        status.Text = "비밀번호 확인 완료 · 이메일 인증 대기 중";
        using var dialog = new EmailVerificationDialog(token);
        return dialog.ShowDialog(this) == DialogResult.OK ? dialog.Code : null;
    }
    void Stop()
    {
        WriteHealth("paused");
        lifetime?.Cancel(); connection?.Dispose(); EndSession(); status.Text = "연결 중지됨";
    }
    async Task Send(object message)
    {
        var c = connection;
        if (c == null || lifetime == null) return;
        try { await c.Send(message, lifetime.Token); }
        catch (Exception ex) { DiagnosticLog.Write("send", ex.GetType().Name + ": " + ex.Message); status.Text = "전송 실패: " + ex.Message; c.Dispose(); }
    }
    void HandleMessage(JsonElement m)
    {
        switch (m.GetProperty("type").GetString())
        {
            case "targets":
                string? selected = (targets.SelectedItem as Target)?.Id;
                targets.BeginUpdate(); targets.Items.Clear();
                foreach (var t in m.GetProperty("targets").EnumerateArray())
                {
                    var item = new Target(t.GetProperty("id").GetString()!, t.GetProperty("name").GetString()!, t.GetProperty("state").GetString()!);
                    targets.Items.Add(item); if (item.Id == selected) targets.SelectedItem = item;
                }
                targets.EndUpdate(); break;
            case "paired":
                EndSession(); paired = true; pairedAt = Environment.TickCount64;
                status.Text = targetMode ? "HOST 접속됨 · 첫 화면 캡처 중" : "TARGET 연결됨 · 첫 화면 수신 대기 중";
                view.Message = targetMode ? "HOST에 화면 전송을 준비하고 있습니다." : "TARGET에 연결되었습니다.\n첫 화면을 기다리고 있습니다…";
                DiagnosticLog.Write("paired", targetMode ? "TARGET" : "HOST");
                UpdateControls();
                if (targetMode) _ = CaptureFrame();
                break;
            case "ended": EndSession(); status.Text = "원격접속 종료 · 서버 연결 유지 중"; UpdateControls(); break;
            case "error": status.Text = m.GetProperty("message").GetString(); break;
            case "frame" when !targetMode && paired:
                if (m.TryGetProperty("capture_error", out var failure))
                {
                    string message = failure.GetString() ?? "TARGET 화면 캡처 실패";
                    ShowFrameProblem("TARGET 화면 캡처 실패\n" + message);
                    break;
                }
                try
                {
                    var bitmap = FrameCodec.Decode(m.GetProperty("data").GetBytesFromBase64());
                    var old = view.Image; view.Image = bitmap; old?.Dispose(); view.Invalidate();
                    lastFrameAt = Environment.TickCount64; receivedFrames++;
                    if (receivedFrames == 1 || captureError != null)
                        DiagnosticLog.Write("frame-received", $"{bitmap.Width}x{bitmap.Height}");
                    captureError = null;
                    bool dark = m.TryGetProperty("nearly_black", out var black) && black.ValueKind == JsonValueKind.True;
                    status.Text = dark ? $"화면 수신 {receivedFrames}회 · TARGET 화면이 거의 검습니다. 잠금·모니터·RDP 상태를 확인하세요."
                        : $"화면 수신 {receivedFrames}회 · {bitmap.Width}×{bitmap.Height} · 화면 클릭 후 제어 · F11 전체화면";
                }
                catch (Exception ex) when (ex is ArgumentException or IOException or InvalidOperationException or KeyNotFoundException or FormatException or System.Runtime.InteropServices.ExternalException)
                {
                    ShowFrameProblem("수신 화면 해석 실패\n" + ex.Message);
                }
                break;
            case "input" when targetMode && paired:
                try { Desktop.Apply(m); } catch (Exception ex) { status.Text = "입력 처리 실패: " + ex.Message; }
                break;
        }
    }
    void EndSession()
    {
        sessionGeneration++;
        lastFrameAt = pairedAt = receivedFrames = sentFrames = nextCaptureAt = 0;
        captureError = null;
        paired = false; if (targetMode) Desktop.Release();
        var old = view.Image; view.Image = null; old?.Dispose();
        view.Message = targetMode ? "TARGET 화면 공유 대기 중입니다." : "HOST에서 TARGET을 선택한 뒤 원격접속을 누르세요.";
    }
    void ShowFrameProblem(string message)
    {
        if (captureError != message)
        {
            DiagnosticLog.Write("frame-error", message);
            _ = Send(new { type = "input", action = "release" });
        }
        captureError = message;
        var old = view.Image; view.Image = null; old?.Dispose();
        view.Message = message; status.Text = message.Replace('\n', ' ');
    }
    void CheckFrameHealth()
    {
        if (!paired || targetMode || captureError != null) return;
        long age = Environment.TickCount64 - (lastFrameAt == 0 ? pairedAt : lastFrameAt);
        if (age < 10000) return;
        ShowFrameProblem(lastFrameAt == 0
            ? "TARGET에 연결됐지만 10초 동안 화면이 도착하지 않았습니다.\nTARGET 상태 표시줄과 client.log를 확인하세요."
            : "10초 동안 새 화면이 도착하지 않아 제어를 일시 중지했습니다.\nTARGET의 잠금·모니터·네트워크 상태를 확인하세요.");
    }
    async Task CaptureFrame()
    {
        if (!targetMode || !paired || sendingFrame || Environment.TickCount64 < nextCaptureAt) return;
        sendingFrame = true;
        var c = connection;
        int generation = sessionGeneration;
        var token = lifetime?.Token ?? CancellationToken.None;
        try
        {
            CapturedFrame frame;
            try
            {
                Rectangle bounds = Screen.PrimaryScreen?.Bounds ?? throw new IOException("활성 모니터를 찾을 수 없습니다.");
                frame = await Task.Run(() => Desktop.Capture(bounds), token);
            }
            catch (Exception ex) when (!token.IsCancellationRequested)
            {
                if (!paired || c == null || !ReferenceEquals(c, connection) || generation != sessionGeneration) return;
                string message = ex.Message;
                if (captureError != message) DiagnosticLog.Write("capture-error", ex.GetType().Name + ": " + message);
                captureError = message;
                status.Text = "화면 캡처 실패: " + message;
                view.Message = status.Text;
                nextCaptureAt = Environment.TickCount64 + 2000;
                // Existing relays forward frame envelopes unchanged, including optional diagnostic fields.
                await c.Send(new { type = "frame", data = Array.Empty<byte>(), capture_error = message }, token);
                return;
            }
            if (paired && c != null && ReferenceEquals(c, connection) && generation == sessionGeneration)
            {
                await c.Send(new { type = "frame", data = frame.Data, nearly_black = frame.NearlyBlack }, token);
                if (generation != sessionGeneration || !ReferenceEquals(c, connection)) return;
                sentFrames++;
                if (sentFrames == 1 || captureError != null)
                    DiagnosticLog.Write("frame-sent", $"{frame.Width}x{frame.Height} bytes={frame.Data.Length} nearlyBlack={frame.NearlyBlack}");
                captureError = null;
                status.Text = frame.NearlyBlack ? $"화면 전송 {sentFrames}회 · 캡처 결과가 거의 검습니다. 모니터·잠금·RDP 상태를 확인하세요."
                    : $"화면 전송 {sentFrames}회 · {frame.Width}×{frame.Height} · 연결 중지 버튼으로 차단";
                view.Message = status.Text;
            }
        }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { }
        catch (Exception ex)
        {
            if (generation == sessionGeneration && ReferenceEquals(c, connection))
            {
                DiagnosticLog.Write("frame-send-error", ex.GetType().Name + ": " + ex.Message);
                status.Text = "화면 전송 실패: " + ex.Message; c?.Dispose();
            }
        }
        finally { sendingFrame = false; }
    }
    async Task Mouse(MouseEventArgs e, bool? down, int wheel = 0)
    {
        if (!CanInput || view.Image == null) return;
        double scale = Math.Min((double)view.ClientSize.Width / view.Image.Width, (double)view.ClientSize.Height / view.Image.Height);
        double w = view.Image.Width * scale, h = view.Image.Height * scale;
        double x = (e.X - (view.ClientSize.Width - w) / 2) / w, y = (e.Y - (view.ClientSize.Height - h) / 2) / h;
        if ((x < 0 || x > 1 || y < 0 || y > 1) && down != false && !view.Capture) return;
        var m = new Dictionary<string, object> { ["type"] = "input", ["action"] = "mouse", ["x"] = Math.Clamp(x, 0, 1), ["y"] = Math.Clamp(y, 0, 1) };
        if (down.HasValue) { m["button"] = e.Button switch { MouseButtons.Left => "left", MouseButtons.Right => "right", _ => "middle" }; m["down"] = down.Value; }
        if (wheel != 0) m["wheel"] = wheel;
        await Send(m);
    }
    void ToggleFull()
    {
        if (role.SelectedIndex == 1) return;
        if (!fullScreen)
        {
            oldBounds = Bounds; oldState = WindowState; WindowState = FormWindowState.Normal;
            FormBorderStyle = FormBorderStyle.None; Bounds = Screen.FromControl(this).Bounds;
            settings.Visible = side.Visible = false; fullScreen = true; view.Focus();
            using var hint = new FullscreenHintDialog();
            hint.ShowDialog(this);
            if (IsDisposed || Disposing) return;
            if (hint.ExitFullscreen && fullScreen) ToggleFull();
            view.Focus();
        }
        else
        {
            FormBorderStyle = FormBorderStyle.Sizable; Bounds = oldBounds; WindowState = oldState;
            settings.Visible = side.Visible = true; fullScreen = false;
        }
    }
}
