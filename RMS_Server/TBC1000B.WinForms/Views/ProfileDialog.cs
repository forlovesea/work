namespace TBC1000B.WinForms.Views;

using TBC1000B.WinForms.Models;
using TBC1000B.WinForms.Services;

public sealed class ProfileDialog : Form
{
    private readonly ListBox _profiles = new();
    private readonly ComboBox _mode = new();
    private readonly ProfileStore _store;
    public string SelectedMode => _mode.SelectedItem?.ToString() ?? "Master";
    public Profile SelectedProfile { get; private set; } = null!;

    public ProfileDialog()
    {
        _store = new ProfileStore(Path.Combine(Environment.CurrentDirectory, "profiles"));
        Text = "프로파일 선택";
        ClientSize = new Size(278, 374);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("맑은 고딕", 9F);

        var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(12), RowCount = 6, ColumnCount = 1 };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 22));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
        Controls.Add(root);
        root.Controls.Add(new Label { Text = "저장된 설치장소 + 시스템", Dock = DockStyle.Fill }, 0, 0);
        _profiles.Dock = DockStyle.Fill;
        ReloadProfiles();
        root.Controls.Add(_profiles, 0, 1);

        var modePanel = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, Padding = new Padding(0, 4, 0, 4) };
        modePanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        modePanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        modePanel.Controls.Add(new Label { Text = "동작 모드:", Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft });
        _mode.Dock = DockStyle.Fill;
        _mode.DropDownStyle = ComboBoxStyle.DropDownList;
        _mode.Items.AddRange(["Master", "Slave"]);
        _mode.SelectedIndex = 0;
        modePanel.Controls.Add(_mode);
        root.Controls.Add(modePanel, 0, 2);

        var manage = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2 };
        manage.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        manage.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        var create = UiTheme.Button("신규 생성"); create.Dock = DockStyle.Fill; create.MinimumSize = new Size(110, 27); create.Margin = new Padding(3); create.Padding = Padding.Empty; create.Click += (_, _) => CreateProfile(); manage.Controls.Add(create);
        var delete = UiTheme.Button("삭제"); delete.Dock = DockStyle.Fill; delete.MinimumSize = new Size(110, 27); delete.Margin = new Padding(3); delete.Padding = Padding.Empty; delete.Click += (_, _) => DeleteProfile(); manage.Controls.Add(delete);
        root.Controls.Add(manage, 0, 3);

        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(0, 3, 0, 3), WrapContents = false };
        var cancel = UiTheme.Button("Cancel"); cancel.Width = 82; cancel.Height = 32; cancel.MinimumSize = new Size(82, 32); cancel.Padding = Padding.Empty; cancel.Margin = new Padding(3, 2, 3, 2); cancel.DialogResult = DialogResult.Cancel;
        var ok = UiTheme.Button("OK"); ok.Width = 82; ok.Height = 32; ok.MinimumSize = new Size(82, 32); ok.Padding = Padding.Empty; ok.Margin = new Padding(3, 2, 3, 2); ok.DialogResult = DialogResult.OK;
        actions.Controls.Add(cancel); actions.Controls.Add(ok);
        root.Controls.Add(actions, 0, 4);
        ok.Click += (_, e) => { if (!SelectProfile()) DialogResult = DialogResult.None; };
        _profiles.DoubleClick += (_, _) => { if (SelectProfile()) { DialogResult = DialogResult.OK; Close(); } };
        AcceptButton = ok; CancelButton = cancel;
    }

    private void ReloadProfiles()
    {
        _profiles.Items.Clear(); foreach (var path in _store.ListProfiles()) _profiles.Items.Add(new ProfileItem(path)); if (_profiles.Items.Count > 0) _profiles.SelectedIndex = 0;
    }
    private bool SelectProfile()
    {
        if (_profiles.SelectedItem is not ProfileItem item) { MessageBox.Show(this, "프로파일을 선택하거나 신규 생성해 주세요.", "안내"); return false; }
        SelectedProfile = _store.Load(item.Path); return true;
    }
    private void CreateProfile()
    {
        using var dialog = new NewProfileDialog(); if (dialog.ShowDialog(this) != DialogResult.OK) return; _store.Create(dialog.SiteName, dialog.SystemName); ReloadProfiles();
    }
    private void DeleteProfile()
    {
        if (_profiles.SelectedItem is not ProfileItem item) return; if (MessageBox.Show(this, $"{item} 프로파일을 삭제합니까?", "삭제", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return; _store.Delete(item.Path); ReloadProfiles();
    }
    private sealed record ProfileItem(string Path) { public override string ToString() => System.IO.Path.GetFileName(Path); }
}

internal sealed class NewProfileDialog : Form
{
    private readonly TextBox _site = new(); private readonly TextBox _system = new();
    public string SiteName => _site.Text.Trim(); public string SystemName => _system.Text.Trim();
    public NewProfileDialog()
    {
        Text = "신규 프로파일 생성"; ClientSize = new Size(340, 140); FormBorderStyle = FormBorderStyle.FixedDialog; StartPosition = FormStartPosition.CenterParent; MaximizeBox = false;
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(12), ColumnCount = 2, RowCount = 3 }; layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 90)); layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); Controls.Add(layout);
        layout.Controls.Add(new Label { Text = "설치 장소", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }); _site.Dock = DockStyle.Fill; layout.Controls.Add(_site);
        layout.Controls.Add(new Label { Text = "축전지명", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }); _system.Dock = DockStyle.Fill; layout.Controls.Add(_system);
        var ok = UiTheme.Button("OK"); ok.DialogResult = DialogResult.OK; var cancel = UiTheme.Button("Cancel"); cancel.DialogResult = DialogResult.Cancel; var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill }; buttons.Controls.AddRange([ok, cancel]); layout.Controls.Add(buttons, 1, 2);
        ok.Click += (_, _) => { if (SiteName.Length == 0 || SystemName.Length == 0) { DialogResult = DialogResult.None; MessageBox.Show(this, "설치 장소와 축전지명을 입력하세요."); } }; AcceptButton = ok; CancelButton = cancel;
    }
}
