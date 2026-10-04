package com.remotecontrol;

import android.app.*;
import android.content.*;
import android.media.projection.*;
import android.os.*;
import android.provider.Settings;
import android.widget.*;

public final class MainActivity extends Activity {
    private TextView status, invitation;
    private CheckBox control;
    private Button start;
    private EditText serverAddress;
    private String relayHost;
    private int relayPort;
    private boolean requestedControl;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable refresh = new Runnable() {
        public void run() {
            status.setText(CaptureService.status);
            invitation.setText(CaptureService.invitation);
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
        serverAddress.setText(getPreferences(MODE_PRIVATE).getString("relay", "")); page.addView(serverAddress);
        control = new CheckBox(this); control.setText("이번 세션에서 터치 제어 허용"); page.addView(control);
        Ui.button(this, page, "터치 제어 권한 설정", v -> new AlertDialog.Builder(this)
                .setTitle("접근성 권한 안내")
                .setMessage("터치 제어를 사용하면 Host가 탭·스와이프·홈·뒤로 가기를 실행할 수 있습니다. 설정에서 RemoteControl 터치 제어를 직접 켜세요. 공유 중지 시 제어도 중단됩니다.")
                .setNegativeButton("취소", null).setPositiveButton("설정 열기", (d, w) -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))).show());
        start = Ui.button(this, page, "화면 공유 시작", v -> startSharing());
        status = Ui.text(this, page, "대기 중");
        invitation = Ui.text(this, page, ""); invitation.setTextIsSelectable(true); invitation.setTextSize(12);
        Ui.button(this, page, "접속 정보 복사", v -> {
            if (!CaptureService.invitation.isEmpty()) {
                ((android.content.ClipboardManager) getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(
                        ClipData.newPlainText("일회용 원격 접속 정보", CaptureService.invitation));
                Toast.makeText(this, "Host에 접속 정보를 전달하세요.", Toast.LENGTH_SHORT).show();
            }
        });
        Ui.button(this, page, "공유 / 연결 즉시 중지", v -> stopService(new Intent(this, CaptureService.class)));
        Ui.text(this, page, "화면 잠금·회전·연결 종료 시 공유가 끝납니다. 다음 연결에는 새 접속 정보가 필요합니다.");
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 11);
    }
    private void startSharing() {
        String[] endpoint = serverAddress.getText().toString().trim().split(":", -1);
        try {
            if (endpoint.length != 2 || !endpoint[0].matches("[a-zA-Z0-9.-]{1,253}")) throw new IllegalArgumentException();
            relayHost = endpoint[0]; relayPort = Integer.parseInt(endpoint[1]);
            if (!Protocol.relayPort(relayPort)) throw new IllegalArgumentException();
        } catch (IllegalArgumentException e) {
            Toast.makeText(this, "도메인:포트 형식으로 입력하세요. 허용 포트: 55000~60000", Toast.LENGTH_LONG).show(); return;
        }
        getPreferences(MODE_PRIVATE).edit().putString("relay", serverAddress.getText().toString().trim()).apply();
        requestedControl = control.isChecked();
        if (requestedControl && ControlService.instance == null) {
            Toast.makeText(this, "접근성 설정에서 터치 제어를 먼저 켜세요.", Toast.LENGTH_LONG).show(); return;
        }
        new AlertDialog.Builder(this).setTitle("화면 공유 시작")
                .setMessage("접속 정보를 가진 Host 한 명에게 화면을 공유합니다." + (requestedControl ? " 터치 제어도 허용합니다." : " 화면 보기만 허용합니다.") + " 다음 시스템 창에서 화면 공유를 허용하세요.")
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
