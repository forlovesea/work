package com.remotecontrol;

import android.app.*;
import android.content.*;
import android.media.projection.*;
import android.os.*;
import android.provider.Settings;
import android.widget.*;

public final class MainActivity extends Activity {
    private TextView status, connectionStatus;
    private CheckBox control;
    private Button start, connectServer;
    private EditText serverAddress, accessKey, deviceName;
    private String relayHost;
    private int relayPort;
    private boolean requestedControl;
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
        LinearLayout page = Ui.page(this, "Target · 제어받는 기기", true);
        Ui.text(this, page, "LTE 또는 Wi-Fi에서 공인 중계서버에 연결합니다. 공유 중에는 화면이 상대방에게 표시됩니다.");
        serverAddress = new EditText(this); serverAddress.setSingleLine(true);
        serverAddress.setHint("중계서버 도메인:포트 (예: relay.example.com:55000)");
        serverAddress.setText(ServerSettings.preferences(this).getString("address", getPreferences(MODE_PRIVATE).getString("relay", "61.105.141.21:55000"))); page.addView(serverAddress);
        accessKey = new EditText(this); accessKey.setSingleLine(true); accessKey.setHint("서버 접속 키 (최초 설정)");
        accessKey.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        accessKey.setText(ServerSettings.secret(this)); page.addView(accessKey);
        deviceName = new EditText(this); deviceName.setSingleLine(true); deviceName.setHint("Host 목록에 표시할 스마트폰 이름");
        deviceName.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(60)});
        deviceName.setText(ServerSettings.preferences(this).getString("name", Build.MODEL)); page.addView(deviceName);
        connectServer = Ui.button(this, page, "서버 연결 / 자동 재접속 시작", v -> {
            if (readEndpoint()) connectServer();
        });
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
        if (request == 10 && result == RESULT_OK && data != null)
            startForegroundService(new Intent(this, CaptureService.class).putExtra("result", result)
                    .putExtra("data", data).putExtra("control", requestedControl)
                    .putExtra("relayHost", relayHost).putExtra("relayPort", relayPort));
    }
    @Override protected void onResume() { super.onResume(); handler.post(refresh); }
    @Override protected void onPause() { handler.removeCallbacks(refresh); super.onPause(); }
}
