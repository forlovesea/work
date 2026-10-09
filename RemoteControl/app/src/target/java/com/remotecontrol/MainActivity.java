package com.remotecontrol;

import android.app.*;
import android.content.*;
import android.media.projection.*;
import android.os.*;
import android.provider.Settings;
import android.widget.*;
import android.text.method.HideReturnsTransformationMethod;
import android.text.method.PasswordTransformationMethod;
import java.io.IOException;

public final class MainActivity extends Activity {
    private TextView status, connectionStatus;
    private CheckBox control;
    private Button start, connectServer;
    private EditText serverAddress, accessKey, deviceName;
    private String relayHost;
    private int relayPort;
    private boolean requestedControl;
    private String pendingKeySave;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable refresh = new Runnable() {
        public void run() {
            status.setText(CaptureService.status);
            connectionStatus.setText(ConnectionService.status);
            connectServer.setEnabled(!ConnectionService.active);
            serverAddress.setEnabled(!ConnectionService.active && CaptureService.instance == null);
            accessKey.setEnabled(!ConnectionService.active && CaptureService.instance == null);
            deviceName.setEnabled(!ConnectionService.active && CaptureService.instance == null);
            start.setEnabled(CaptureService.instance == null);
            control.setEnabled(CaptureService.instance == null);
            handler.postDelayed(this, 500);
        }
    };
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        Diagnostics.installCrashHandler(this, "target");
        Diagnostics.record(this, "target", "app started", null);
        LinearLayout page = Ui.page(this, "Target · 제어받는 기기", true);
        Ui.headerAction(this, page, "진단 로그 공유", v -> shareDiagnostics());
        Ui.text(this, page, "LTE 또는 Wi-Fi에서 공인 중계서버에 연결합니다. 공유 중에는 화면이 상대방에게 표시됩니다.");
        serverAddress = new EditText(this); serverAddress.setSingleLine(true);
        serverAddress.setHint("중계서버 도메인:포트 (예: relay.example.com:55000)");
        serverAddress.setText(ServerSettings.preferences(this).getString("address", getPreferences(MODE_PRIVATE).getString("relay", "61.105.141.21:55000"))); page.addView(serverAddress);
        LinearLayout keyRow = new LinearLayout(this);
        keyRow.setOrientation(LinearLayout.HORIZONTAL);
        accessKey = new EditText(this); accessKey.setSingleLine(true); accessKey.setHint("서버 접속 키 (최초 설정)");
        accessKey.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        accessKey.setText(ServerSettings.secret(this));
        keyRow.addView(accessKey, new LinearLayout.LayoutParams(0, -2, 1));
        CheckBox showKey = new CheckBox(this); showKey.setText("표시");
        showKey.setOnCheckedChangeListener((button, checked) -> setKeyVisibility(accessKey, checked));
        keyRow.addView(showKey);
        Ui.button(this, keyRow, "키 위치", v -> showAccessKeyHelp());
        page.addView(keyRow);
        LinearLayout keyFileRow = new LinearLayout(this);
        keyFileRow.setOrientation(LinearLayout.HORIZONTAL);
        addKeyFileButton(keyFileRow, "키 파일 저장", v -> saveKeyFile());
        addKeyFileButton(keyFileRow, "키 파일 불러오기", v -> selectKeyFile(31));
        addKeyFileButton(keyFileRow, "키파일 삭제", v -> selectKeyFile(32));
        page.addView(keyFileRow);
        deviceName = new EditText(this); deviceName.setSingleLine(true); deviceName.setHint("Host 목록에 표시할 스마트폰 이름");
        deviceName.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(60)});
        deviceName.setText(ServerSettings.preferences(this).getString("name", Build.MODEL)); page.addView(deviceName);
        connectServer = Ui.button(this, page, "서버 연결 / 자동 재접속 시작", v -> {
            if (readEndpoint()) connectServer();
        });
        Ui.text(this, page, "Host의 화면 켜짐 유지 옵션을 사용하면 화면 공유 연결 중 자동 화면 꺼짐을 방지합니다. 연결 종료 또는 유지 신호 중단 시 해제됩니다.");
        connectionStatus = Ui.text(this, page, ConnectionService.status);
        control = new CheckBox(this); control.setText("이번 세션에서 터치 제어 허용"); page.addView(control);
        Ui.button(this, page, "터치 제어 권한 설정", v -> new AlertDialog.Builder(this)
                .setTitle("접근성 권한 안내")
                .setMessage("터치 제어를 사용하면 Host가 탭·스와이프·홈·뒤로 가기를 실행할 수 있습니다. 설정에서 RemoteControl 터치 제어를 직접 켜세요. 공유 중지 시 제어도 중단됩니다.")
                .setNegativeButton("취소", null).setPositiveButton("설정 열기", (d, w) -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))).show());
        start = Ui.button(this, page, "화면 공유 시작", v -> startSharing());
        status = Ui.text(this, page, "대기 중");
        Ui.button(this, page, "공유 / 연결 즉시 중지", v -> stopConnections());
        Ui.button(this, page, "프로그램 종료", v -> {
            stopConnections();
            if (ControlService.instance != null) ControlService.instance.disableSelf();
            finishAndRemoveTask();
        });
        Ui.text(this, page, "같은 서버 접속 키를 사용하는 Host의 목록에 이 기기가 표시됩니다. 화면 공유를 승인하면 Host에서 선택해 연결할 수 있습니다. 인터넷 복구 시 자동 재접속합니다.");
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 11);
    }
    private void stopConnections() {
        stopService(new Intent(this, CaptureService.class));
        stopService(new Intent(this, ConnectionService.class));
    }
    private void connectServer() {
        startForegroundService(new Intent(this, ConnectionService.class).putExtra("host", relayHost).putExtra("port", relayPort));
    }
    private void addKeyFileButton(LinearLayout row, String label, android.view.View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(11);
        button.setMinWidth(0);
        button.setPadding(2, 0, 2, 0);
        button.setOnClickListener(listener);
        row.addView(button, new LinearLayout.LayoutParams(0, -2, 1));
    }
    private void saveKeyFile() {
        String key = accessKey.getText().toString().trim();
        if (!key.matches("[0-9a-fA-F]{64}")) {
            Toast.makeText(this, "서버 접속 키를 먼저 입력하세요. 64자리 hex 형식이어야 합니다.", Toast.LENGTH_LONG).show();
            return;
        }
        pendingKeySave = key;
        launchKeyFilePicker(ServerKeyFile.createIntent(), 30);
    }
    private void selectKeyFile(int request) {
        launchKeyFilePicker(ServerKeyFile.openIntent(), request);
    }
    private void launchKeyFilePicker(Intent intent, int request) {
        try {
            startActivityForResult(intent, request);
        } catch (android.content.ActivityNotFoundException error) {
            pendingKeySave = null;
            Toast.makeText(this, "이 기기에 파일 선택 앱이 없어 키 파일을 처리할 수 없습니다.", Toast.LENGTH_LONG).show();
        }
    }
    private void handleKeyFileResult(int request, int result, Intent data) {
        if (request == 30 && result != RESULT_OK) pendingKeySave = null;
        if (result != RESULT_OK || data == null || data.getData() == null) return;
        android.net.Uri uri = data.getData();
        try {
            if (request == 30) {
                if (pendingKeySave == null) throw new IOException("저장할 키가 없습니다. 다시 시도하세요.");
                ServerKeyFile.write(this, uri, pendingKeySave);
                pendingKeySave = null;
                Toast.makeText(this, "공유 위치에 서버 접속 키를 저장했습니다.", Toast.LENGTH_LONG).show();
            } else if (request == 31) {
                accessKey.setText(ServerKeyFile.read(this, uri));
                Toast.makeText(this, "서버 접속 키를 불러왔습니다. 서버 연결 시 앱에도 저장됩니다.", Toast.LENGTH_LONG).show();
            } else if (request == 32) {
                new AlertDialog.Builder(this)
                        .setTitle("키 파일 삭제")
                        .setMessage("선택한 파일을 삭제하고 이 앱에 저장된 서버 접속 키도 지울까요?")
                        .setNegativeButton("취소", null)
                        .setPositiveButton("삭제", (dialog, which) -> {
                            try {
                                ServerKeyFile.delete(this, uri);
                                ServerSettings.clearSecret(this);
                                accessKey.setText("");
                                Toast.makeText(this, "키 파일과 앱에 저장된 키를 삭제했습니다.", Toast.LENGTH_LONG).show();
                            } catch (IOException error) {
                                Toast.makeText(this, "키 파일을 삭제할 수 없습니다: " + error.getMessage(), Toast.LENGTH_LONG).show();
                            }
                        }).show();
            }
        } catch (IOException error) {
            pendingKeySave = null;
            Toast.makeText(this, "키 파일 작업 실패: " + error.getMessage(), Toast.LENGTH_LONG).show();
        }
    }
    private boolean readEndpoint() {
        String[] endpoint = serverAddress.getText().toString().trim().split(":", -1);
        try {
            if (endpoint.length != 2 || !endpoint[0].matches("[a-zA-Z0-9.-]{1,253}")) throw new IllegalArgumentException();
            relayHost = endpoint[0]; relayPort = Integer.parseInt(endpoint[1]);
            if (!Protocol.relayPort(relayPort)) throw new IllegalArgumentException();
        } catch (IllegalArgumentException e) {
            Toast.makeText(this, "도메인:포트 형식으로 입력하세요. 허용 포트: 55000~60000", Toast.LENGTH_LONG).show(); return false;
        }
        getPreferences(MODE_PRIVATE).edit().putString("relay", serverAddress.getText().toString().trim()).apply();
        try {
            String name = deviceName.getText().toString().trim();
            if (name.isEmpty() || name.matches(".*[\\p{Cntrl}].*")) throw new IllegalArgumentException("스마트폰 이름을 입력하세요.");
            ServerSettings.save(this, serverAddress.getText().toString().trim(), accessKey.getText().toString().trim(), name);
        } catch (Exception error) {
            Toast.makeText(this, error instanceof IllegalArgumentException ? error.getMessage() : "설정을 저장할 수 없습니다.", Toast.LENGTH_LONG).show();
            return false;
        }
        return true;
    }
    private void showAccessKeyHelp() {
        new AlertDialog.Builder(this)
                .setTitle("서버 접속 키 위치")
                .setMessage("Ubuntu 서버의 기본 키 파일은 /etc/remotecontrol/access.key 입니다.\n\n서버에서 다음 명령으로 확인하세요:\n\nsudo cat /etc/remotecontrol/access.key\n\n서버 설정에서 --access-key-file 경로를 따로 지정했다면 그 파일을 확인하세요. 이 키는 Host와 Target에 동일하게 입력하며, 허용한 사용자에게만 안전하게 전달하세요.")
                .setPositiveButton("확인", null).show();
    }
    private void shareDiagnostics() {
        try {
            Diagnostics.share(this);
        } catch (IOException error) {
            Toast.makeText(this, "진단 로그를 읽을 수 없습니다: " + error.getMessage(), Toast.LENGTH_LONG).show();
        }
    }
    private static void setKeyVisibility(EditText field, boolean visible) {
        int selection = field.getSelectionStart();
        field.setTransformationMethod(visible
                ? HideReturnsTransformationMethod.getInstance()
                : PasswordTransformationMethod.getInstance());
        field.setSelection(Math.max(0, Math.min(selection, field.length())));
    }
    private void startSharing() {
        if (!readEndpoint()) return;
        if (!ConnectionService.active) connectServer();
        requestedControl = control.isChecked();
        if (requestedControl && ControlService.instance == null) {
            Toast.makeText(this, "접근성 설정에서 터치 제어를 먼저 켜세요.", Toast.LENGTH_LONG).show(); return;
        }
        new AlertDialog.Builder(this).setTitle("화면 공유 시작")
                .setMessage("같은 서버 접속 키를 사용하는 Host 한 명이 목록에서 이 기기를 선택해 화면을 볼 수 있습니다." + (requestedControl ? " 터치 제어도 허용합니다." : " 화면 보기만 허용합니다.") + " 다음 시스템 창에서 화면 공유를 허용하세요.")
                .setNegativeButton("취소", null).setPositiveButton("계속", (d, w) -> {
                    MediaProjectionManager manager = (MediaProjectionManager) getSystemService(MEDIA_PROJECTION_SERVICE);
                    Intent request = Build.VERSION.SDK_INT >= 34
                            ? manager.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay()) : manager.createScreenCaptureIntent();
                    startActivityForResult(request, 10);
                }).show();
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request >= 30 && request <= 32) {
            handleKeyFileResult(request, result, data);
            return;
        }
        if (request == 10 && result == RESULT_OK && data != null)
            startForegroundService(new Intent(this, CaptureService.class).putExtra("result", result)
                    .putExtra("data", data).putExtra("control", requestedControl)
                    .putExtra("relayHost", relayHost).putExtra("relayPort", relayPort));
    }
    @Override protected void onResume() { super.onResume(); handler.post(refresh); }
    @Override protected void onPause() { handler.removeCallbacks(refresh); super.onPause(); }
}
