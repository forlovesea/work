using System.Diagnostics;

namespace SafeChild;

public sealed partial class MainForm
{
    private TabPage _messagesPage = null!;
    private readonly ComboBox _messageDomain = new() { DropDownStyle = ComboBoxStyle.DropDownList, Dock = DockStyle.Fill, DisplayMember = nameof(BlockEntry.Domain) };
    private readonly TextBox _messageEditor = new() { Multiline = true, Dock = DockStyle.Fill, ScrollBars = ScrollBars.Vertical, MaxLength = 2000, AcceptsReturn = true, Font = new Font("맑은 고딕", 12F), PlaceholderText = "자녀에게 전하고 싶은 말을 적어주세요.\r\n줄을 나누면 팝업에도 그대로 표시됩니다." };
    private readonly Label _messageConnection = new() { AutoSize = true, ForeColor = Color.FromArgb(15, 118, 110) };
    private BrowserMessageServer? _messageBridge;
    private string? _messageBridgeError;
    private bool _startingMessageBridge;
    private ChildMessagePopup? _childMessagePopup;
    private readonly Dictionary<string, long> _messageCooldowns = new(StringComparer.OrdinalIgnoreCase);
    private readonly Label _messageHint = new() { AutoSize = true, ForeColor = Color.FromArgb(146, 64, 64) };

    private TabPage BuildMessagesTab()
    {
        var page = new TabPage("전달 메시지") { BackColor = Color.FromArgb(255, 249, 244), AutoScroll = true };
        var layout = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, ColumnCount = 1, RowCount = 7, Padding = new Padding(24) };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 240));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.Controls.Add(new Label { Text = "차단 안내에 따뜻한 한마디를 더해 주세요", AutoSize = true, Font = new Font(Font.FontFamily, 15F, FontStyle.Bold), ForeColor = Color.FromArgb(146, 64, 64), Margin = new Padding(0, 0, 0, 12) }, 0, 0);
        var help = new Label { AutoSize = true, Text = "도메인을 선택해 메시지를 저장하세요. 해당 도메인이 차단 중일 때 자녀가 접속하면 팝업으로 전달됩니다.\n메시지를 비워 저장하면 팝업을 끕니다. 차단 설정은 그대로 유지됩니다. (최대 2,000자)", ForeColor = Color.FromArgb(100, 80, 70), Margin = new Padding(0, 0, 0, 14) };
        layout.Controls.Add(help, 0, 1);
        layout.Controls.Add(_messageDomain, 0, 2);
        _messageDomain.SelectedIndexChanged += (_, _) => UpdateMessageEditor();
        layout.Controls.Add(_messageEditor, 0, 3);
        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true, Margin = new Padding(0, 12, 0, 12) };
        var save = new Button { Text = "메시지 저장", AutoSize = true };
        var preview = new Button { Text = "자녀 화면 미리보기", AutoSize = true };
        var clear = new Button { Text = "메시지 삭제", AutoSize = true };
        StyleDomainAction(save, Color.FromArgb(85, 119, 101), Color.White, Color.FromArgb(85, 119, 101));
        StyleDomainAction(preview, Color.FromArgb(255, 237, 213), Color.FromArgb(154, 77, 32), Color.FromArgb(254, 215, 170));
        StyleDomainAction(clear, Color.FromArgb(255, 241, 242), Color.FromArgb(190, 18, 60), Color.FromArgb(254, 205, 211));
        save.Click += (_, _) => SaveChildMessage(false);
        clear.Click += (_, _) => SaveChildMessage(true);
        preview.Click += (_, _) =>
        {
            if (!_adminUnlocked || _messageDomain.SelectedItem is not BlockEntry item) return;
            if (string.IsNullOrWhiteSpace(_messageEditor.Text)) { MessageBox.Show(this, "미리 볼 메시지를 입력하세요."); return; }
            ShowChildMessage(new ChildMessageNotice(item.Domain, _messageEditor.Text.Trim()));
        };
        actions.Controls.AddRange([save, preview, clear]);
        layout.Controls.Add(actions, 0, 4);
        var connection = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, FlowDirection = FlowDirection.TopDown, WrapContents = false, BackColor = Color.FromArgb(255, 243, 230), Padding = new Padding(12) };
        connection.Controls.Add(new Label { Text = "Chrome·Edge에서 접속 감지를 사용하려면", AutoSize = true, Font = new Font(Font, FontStyle.Bold), ForeColor = Color.FromArgb(146, 64, 14) });
        var instructions = new Label { AutoSize = true, Text = "브라우저 확장 관리 → 개발자 모드 → ‘압축해제된 확장 프로그램 로드’에서 아래 확장 폴더를 선택하세요.\n자녀가 사용하는 각 브라우저 프로필에 설치해야 합니다. 확장이 없으면 차단만 동작하고 메시지는 뜨지 않습니다.", Margin = new Padding(0, 6, 0, 6) };
        connection.Controls.Add(instructions);
        var tools = new FlowLayoutPanel { AutoSize = true };
        var folder = new Button { Text = "확장 폴더 열기", AutoSize = true };
        folder.Click += (_, _) =>
        {
            var path = Path.Combine(AppContext.BaseDirectory, "BrowserExtension");
            if (!Directory.Exists(path)) { MessageBox.Show(this, "확장 폴더가 없습니다. 앱을 다시 빌드하세요."); return; }
            Process.Start(new ProcessStartInfo("explorer.exe") { Arguments = $"\"{path}\"", UseShellExecute = true });
        };
        var retry = new Button { Text = "연결 다시 확인", AutoSize = true };
        retry.Click += async (_, _) =>
        {
            retry.Enabled = false;
            retry.Text = "확인 중…";
            try
            {
                await StartMessageBridgeAsync();
                if (IsDisposed || Disposing) return;
                var clients = _messageBridge?.ClientCount ?? 0;
                var message = _startingMessageBridge
                    ? "접속 감지 기능을 시작하고 있습니다.\n잠시 후 다시 확인해주세요."
                    : _messageBridgeError is not null
                        ? $"접속 감지 기능을 시작하지 못했습니다.\n\n오류 내용: {_messageBridgeError}\n\n오류 원인을 해결한 후 ‘연결 다시 확인’을 눌러주세요."
                        : clients > 0
                            ? $"현재 브라우저 {clients}개가 연결되어 있습니다.\n\n메시지가 저장된 도메인이 차단 중일 때 접속하면 전달 메시지를 표시합니다."
                            : "앱의 접속 감지 기능은 실행 중입니다.\n현재 연결된 브라우저는 없습니다.\n\n자녀가 사용하는 Chrome 또는 Edge에서 SafeChild 확장이 설치되어 있고 켜져 있는지 확인해주세요.\n확장을 켠 뒤 잠시 기다렸다가 다시 확인해주세요.";
                MessageBox.Show(this, message, "전달 메시지 · 연결 확인", MessageBoxButtons.OK,
                    !_startingMessageBridge && _messageBridgeError is not null ? MessageBoxIcon.Warning : MessageBoxIcon.Information);
            }
            finally
            {
                if (!retry.IsDisposed) { retry.Text = "연결 다시 확인"; retry.Enabled = true; }
            }
        };
        tools.Controls.AddRange([folder, retry]); connection.Controls.Add(tools); connection.Controls.Add(_messageConnection);
        layout.Controls.Add(_messageHint, 0, 5);
        layout.Controls.Add(connection, 0, 6);
        layout.SizeChanged += (_, _) =>
        {
            var width = Math.Max(200, layout.ClientSize.Width - layout.Padding.Horizontal - 32);
            help.MaximumSize = instructions.MaximumSize = _messageConnection.MaximumSize = new Size(width, 0);
        };
        page.Controls.Add(layout);
        RefreshMessageDomains();
        return page;
    }

    private void UpdateMessageEditor()
    {
        var item = _messageDomain.SelectedItem as BlockEntry;
        _messageEditor.Enabled = true;
        _messageEditor.ReadOnly = item is null;
        _messageEditor.Text = item?.ChildMessage ?? "";
        _messageHint.Text = item is null
            ? "먼저 ‘URL/도메인 차단’에서 도메인을 등록하세요. 등록 후 여기에서 메시지를 작성할 수 있습니다."
            : $"{item.Domain}에 전달할 메시지 · 줄바꿈은 팝업에도 그대로 표시됩니다.";
    }

    private void RefreshMessageDomains()
    {
        var selected = (_messageDomain.SelectedItem as BlockEntry)?.Domain;
        _messageDomain.DataSource = _store.Settings.Domains.ToList();
        if (selected is not null)
            for (var i = 0; i < _messageDomain.Items.Count; i++)
                if (_messageDomain.Items[i] is BlockEntry entry && entry.Domain == selected) { _messageDomain.SelectedIndex = i; break; }
        if (_messageDomain.SelectedIndex < 0 && _messageDomain.Items.Count > 0) _messageDomain.SelectedIndex = 0;
        UpdateMessageEditor();
    }

    private void SaveChildMessage(bool clear)
    {
        if (!_adminUnlocked || _messageDomain.SelectedItem is not BlockEntry item) return;
        if (clear && MessageBox.Show(this, "이 도메인의 전달 메시지만 삭제할까요?", "메시지 삭제", MessageBoxButtons.YesNo) != DialogResult.Yes) return;
        var previous = item.ChildMessage;
        item.ChildMessage = clear ? "" : _messageEditor.Text.Trim();
        try { _store.Save(); }
        catch (Exception ex) { item.ChildMessage = previous; MessageBox.Show(this, ex.Message, "메시지 저장 실패"); return; }
        _messageEditor.Text = item.ChildMessage;
        _messageCooldowns.Remove(item.Domain);
        MessageBox.Show(this, string.IsNullOrWhiteSpace(item.ChildMessage) ? "메시지를 지웠습니다. 도메인 차단은 유지됩니다." : "메시지를 저장했습니다.", "전달 메시지");
    }

    private async Task StartMessageBridgeAsync()
    {
        if (_messageBridge is not null || _startingMessageBridge) { UpdateMessageConnection(); return; }
        _startingMessageBridge = true;
        var server = new BrowserMessageServer(
            () => OnUiAsync(() => ChildMessagePolicy.Domains(_store.Settings, DateTimeOffset.UtcNow)),
            url => OnUiAsync(() =>
            {
                var notice = ChildMessagePolicy.Resolve(_store.Settings, url, DateTimeOffset.UtcNow);
                if (notice is null) return false;
                var now = Environment.TickCount64;
                if (_messageCooldowns.TryGetValue(notice.Domain, out var last) && now - last < 30000) return false;
                _messageCooldowns[notice.Domain] = now;
                ShowChildMessage(notice);
                return true;
            }));
        try { await server.StartAsync(); _messageBridge = server; _messageBridgeError = null; }
        catch (Exception ex) { await server.DisposeAsync(); _messageBridgeError = ex.Message; }
        finally { _startingMessageBridge = false; UpdateMessageConnection(); }
    }

    private void UpdateMessageConnection()
    {
        _messageConnection.Text = _messageBridgeError is not null ? $"접속 감지 연결 오류: {_messageBridgeError}"
            : _messageBridge?.ClientCount > 0 ? $"브라우저 {_messageBridge.ClientCount}개 연결됨 · 메시지 전달 준비 완료"
            : "브라우저 연결 대기 중 · 확장 설치 여부를 확인하세요.";
    }

    private void ShowChildMessage(ChildMessageNotice notice)
    {
        if (_childMessagePopup is { IsDisposed: false } existing)
        {
            existing.Display(notice.Domain, notice.Message); existing.Activate(); return;
        }
        var popup = new ChildMessagePopup(notice.Domain, notice.Message);
        _childMessagePopup = popup;
        popup.FormClosed += (_, _) => _childMessagePopup = null;
        popup.Show();
    }
}
