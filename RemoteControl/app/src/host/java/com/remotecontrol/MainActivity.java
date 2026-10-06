package com.remotecontrol;

import android.app.Activity;
import android.graphics.*;
import android.os.*;
import android.view.MotionEvent;
import android.widget.*;
import java.io.*;
import java.net.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import javax.net.ssl.SSLSocket;

public final class MainActivity extends Activity {
    private EditText serverAddress, accessKey;
    private LinearLayout settingsPanel, deviceRows, page;
    private ScrollView deviceList;
    private android.view.View title;
    private boolean browsing, loading, fullScreen, smallView;
    private volatile int browseGeneration;
    private String listHost, listKey;
    private int listPort;
    private volatile SSLSocket listing;
    private final Runnable listTick = new Runnable() {
        public void run() { if (browsing) refreshDevices(); main.postDelayed(this, 5000); }
    };
    private TextView status;
    private TextView healthBar;
    private final ConnectionHealth health = new ConnectionHealth();
    private final Runnable healthTick = new Runnable() {
        @Override public void run() {
            long now = SystemClock.elapsedRealtime();
            if (health.timedOut(now)) disconnect("Target가 10초 동안 응답하지 않아 연결을 종료했습니다.");
            else if (health.needsPing(now)) sendPing(now);
            controlAllowed = health.canSendControl(now);
            renderHealth();
            main.postDelayed(this, 500);
        }
    };
    private ImageView screen;
    private Button connect;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ThreadPoolExecutor commands = new ThreadPoolExecutor(1, 1, 0, TimeUnit.SECONDS,
            new ArrayBlockingQueue<>(8), new ThreadPoolExecutor.DiscardPolicy());
    private final AtomicBoolean pendingFrame = new AtomicBoolean();
    private volatile SSLSocket socket;
    private volatile SSLSocket relay;
    private volatile DataOutputStream output;
    private volatile int generation;
    private volatile boolean controlAllowed;
    private Bitmap current;
    private float startX, startY;
    private long downTime;
    private boolean touching;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        page = Ui.page(this, "Host · 원격 스마트폰");
        title = page.getChildAt(0);
        settingsPanel = new LinearLayout(this); settingsPanel.setOrientation(LinearLayout.VERTICAL); page.addView(settingsPanel);
        serverAddress = new EditText(this); serverAddress.setSingleLine(true); serverAddress.setHint("중계서버 주소:포트");
        serverAddress.setText(ServerSettings.preferences(this).getString("address", "61.105.141.21:55000")); settingsPanel.addView(serverAddress);
        accessKey = new EditText(this); accessKey.setSingleLine(true); accessKey.setHint("서버 접속 키 (최초 설정)");
        accessKey.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        accessKey.setText(ServerSettings.secret(this)); settingsPanel.addView(accessKey);
        connect = Ui.button(this, settingsPanel, "서버 연결 / 목록 새로고침", v -> browse());
        status = Ui.text(this, page, "서버에 연결하면 Target 목록이 표시됩니다.");
        deviceList = new ScrollView(this); deviceRows = new LinearLayout(this); deviceRows.setOrientation(LinearLayout.VERTICAL);
        deviceList.addView(deviceRows); page.addView(deviceList, new LinearLayout.LayoutParams(-1, dp(140)));
        LinearLayout navigation = new LinearLayout(this); page.addView(navigation);
        toolbarButton(navigation, "뒤로", () -> command(Protocol.BACK, 0, 0, 0, 0, 1));
        toolbarButton(navigation, "홈", () -> command(Protocol.HOME, 0, 0, 0, 0, 1));
        toolbarButton(navigation, "화면 보기", this::viewOptions);
        toolbarButton(navigation, "연결 종료", () -> disconnect("연결을 종료했습니다.", false));
        screen = new ImageView(this); screen.setBackgroundColor(Color.rgb(15, 23, 42));
        screen.setScaleType(ImageView.ScaleType.MATRIX);
        screen.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> fitImage());
        page.addView(screen, new LinearLayout.LayoutParams(-1, 0, 1));
        healthBar = new TextView(this);
        healthBar.setTextSize(13); healthBar.setTypeface(null, Typeface.BOLD);
        healthBar.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
                .setTitle("제어 연결 품질 · 10단계")
                .setMessage("초록 1~2: 매우 원활 / 원활\n노랑 3~4: 약간의 지연 / 지연\n주황 5~7: 느림 / 끊김 주의 / 매우 느림\n빨강 8~10: 심한 지연 / 응답 중단 / 장시간 무응답\n\n같은 색 계열에서 진할수록 상태가 나쁩니다. 최근 10회 응답의 속도, 변동폭, 700ms 이상 지연 응답 비율과 현재 응답 대기를 종합합니다.\n\n변동 = 인접 응답 시간 차이의 평균\n지연 응답 = 700ms 이상 응답 비율 (패킷 손실률이 아님)\n5초 무응답 시 제어 차단, 10초 무응답 시 종료합니다.\n\n연결/제어 준비 상태의 추정치이며 개별 터치의 실제 실행 성공을 뜻하지 않습니다.")
                .setPositiveButton("확인", null).show());
        healthBar.setGravity(android.view.Gravity.CENTER_VERTICAL);
        int padding = Math.round(12 * getResources().getDisplayMetrics().density);
        healthBar.setPadding(padding, padding, padding, padding);
        healthBar.setMinHeight(Math.round(52 * getResources().getDisplayMetrics().density));
        page.addView(healthBar, new LinearLayout.LayoutParams(-1, -2));
        renderHealth();
        screen.setOnTouchListener((view, event) -> {
            if (current == null || !controlAllowed || !health.canSendControl(SystemClock.elapsedRealtime())) return true;
            float[] point = { event.getX(), event.getY() };
            Matrix inverse = new Matrix(); screen.getImageMatrix().invert(inverse); inverse.mapPoints(point);
            float x = point[0] / current.getWidth(), y = point[1] / current.getHeight();
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                touching = Protocol.coordinate(x) && Protocol.coordinate(y);
                startX = x; startY = y; downTime = SystemClock.elapsedRealtime();
            } else if (event.getActionMasked() == MotionEvent.ACTION_UP && touching) {
                touching = false;
                if (Protocol.coordinate(x) && Protocol.coordinate(y)) command(Protocol.GESTURE, startX, startY, x, y,
                        (int) Math.max(1, Math.min(2000, SystemClock.elapsedRealtime() - downTime)));
                view.performClick();
            } else if (event.getActionMasked() == MotionEvent.ACTION_CANCEL) touching = false;
            return true;
        });
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private void toolbarButton(LinearLayout row, String label, Runnable action) {
        Button button = new Button(this); button.setText(label); button.setTextSize(12); button.setMinWidth(0);
        row.addView(button, new LinearLayout.LayoutParams(0, -2, 1)); button.setOnClickListener(v -> action.run());
    }
    private void viewOptions() {
        new android.app.AlertDialog.Builder(this).setTitle("원격 화면 보기")
                .setSingleChoiceItems(new String[]{"화면에 맞춤", "전체화면 보기", "작게 보기"}, fullScreen ? 1 : smallView ? 2 : 0,
                        (d, which) -> { setViewMode(which); d.dismiss(); }).setNegativeButton("닫기", null).show();
    }
    private void setViewMode(int mode) {
        fullScreen = mode == 1; smallView = mode == 2; touching = false;
        int visibility = fullScreen ? android.view.View.GONE : android.view.View.VISIBLE;
        title.setVisibility(visibility);
        int setupVisibility = fullScreen || socket != null ? android.view.View.GONE : android.view.View.VISIBLE;
        settingsPanel.setVisibility(setupVisibility); deviceList.setVisibility(setupVisibility);
        status.setVisibility(visibility); healthBar.setVisibility(visibility);
        if (Build.VERSION.SDK_INT >= 30) {
            android.view.WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) {
                controller.setSystemBarsBehavior(android.view.WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
                if (fullScreen) controller.hide(android.view.WindowInsets.Type.systemBars());
                else controller.show(android.view.WindowInsets.Type.systemBars());
            }
        } else getWindow().getDecorView().setSystemUiVisibility(fullScreen
                ? android.view.View.SYSTEM_UI_FLAG_FULLSCREEN | android.view.View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | android.view.View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY : android.view.View.SYSTEM_UI_FLAG_VISIBLE);
        screen.post(this::fitImage);
    }
    private void fitImage() {
        if (current == null || screen.getWidth() == 0 || screen.getHeight() == 0) return;
        float scale = Math.min((float) screen.getWidth() / current.getWidth(), (float) screen.getHeight() / current.getHeight());
        if (smallView) scale *= 0.55f;
        Matrix matrix = new Matrix(); matrix.setScale(scale, scale);
        matrix.postTranslate((screen.getWidth() - current.getWidth() * scale) / 2f,
                (screen.getHeight() - current.getHeight() * scale) / 2f);
        screen.setImageMatrix(matrix);
    }
    private void browse() {
        try {
            String[] endpoint = ServerSettings.endpoint(serverAddress.getText().toString());
            String key = accessKey.getText().toString().trim();
            ServerSettings.save(this, serverAddress.getText().toString().trim(), key, "Host");
            disconnect("중계서버 연결 중…", false);
            browseGeneration++; loading = false;
            if (listing != null) try { listing.close(); } catch (IOException ignored) {}
            deviceRows.removeAllViews();
            listHost = endpoint[0]; listPort = Integer.parseInt(endpoint[1]); listKey = key; browsing = true;
            ((android.view.inputmethod.InputMethodManager) getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(accessKey.getWindowToken(), 0);
            refreshDevices();
        } catch (Exception error) { status.setText(error instanceof IllegalArgumentException ? error.getMessage() : "서버 설정을 저장할 수 없습니다."); }
    }
    private void refreshDevices() {
        if (loading || !browsing) return;
        loading = true;
        final int request = browseGeneration;
        final String host = listHost, key = listKey; final int port = listPort;
        new Thread(() -> {
            try (SSLSocket connection = Relay.socket()) {
                listing = connection;
                if (request != browseGeneration) return;
                org.json.JSONArray rows = Directory.open(connection, host, port, Directory.request("LIST", key, null)).getJSONArray("devices");
                main.post(() -> {
                    if (request != browseGeneration || !browsing) return;
                    loading = false; deviceRows.removeAllViews();
                    if (rows.length() == 0) Ui.text(this, deviceRows, "접속 중인 Target이 없습니다. Target에서 서버 연결을 시작하세요.");
                    for (int i = 0; i < rows.length(); i++) {
                        org.json.JSONObject item = rows.optJSONObject(i); if (item == null) continue;
                        String id = item.optString("id"), state = item.optString("state");
                        String name = item.optString("name", "Target");
                        String label = state.equals("ready") ? "연결 가능" : state.equals("busy") ? "사용 중" : "화면 공유 승인 필요";
                        Button device = Ui.button(this, deviceRows, name + " · " + label + " · " + id.substring(0, Math.min(6, id.length())),
                                v -> connect(id, name, host, port, key));
                        device.setEnabled(state.equals("ready") && socket == null && relay == null);
                    }
                    if (socket == null && relay == null) status.setText("서버 연결됨 · Target " + rows.length() + "대 · 5초마다 갱신");
                });
            } catch (Exception error) {
                main.post(() -> {
                    if (request != browseGeneration) return;
                    loading = false; deviceRows.removeAllViews();
                    Ui.text(this, deviceRows, "목록을 불러오지 못했습니다. 자동으로 다시 시도합니다.");
                    if (socket == null && relay == null) status.setText("서버 연결 실패: " + (error instanceof IOException ? error.getMessage() : error.getClass().getSimpleName()));
                });
            }
        }, "host-directory").start();
    }
    private void connect(String deviceId, String deviceName, String host, int port, String key) {
        if (socket != null || relay != null || !connect.isEnabled()) return;
        disconnect("연결 중…", false); connect.setEnabled(false);
        health.connecting(); renderHealth();
        final int session = generation;
        new Thread(() -> {
            SSLSocket link = null;
            SSLSocket upstream = null;
            try {
                upstream = Relay.socket();
                synchronized (this) {
                    if (session != generation) { upstream.close(); return; }
                    relay = upstream;
                }
                org.json.JSONObject selected = Directory.open(upstream, host, port, Directory.request("CONNECT", key, deviceId));
                String fingerprint = selected.getString("fingerprint"), token = selected.getString("token");
                if (!fingerprint.matches("[0-9a-fA-F]{64}") || !token.matches("[0-9a-f]{32}")) throw new IOException("잘못된 서버 응답");
                if (!Relay.line(upstream).equals("PAIRED")) throw new IOException("Target 연결 실패");
                upstream.setSoTimeout(0);
                Socket tunnel = Relay.localTunnel(upstream);
                try { link = (SSLSocket) Tls.client(fingerprint).getSocketFactory().createSocket(tunnel, "target", 0, true); }
                catch (Exception e) { tunnel.close(); throw e; }
                synchronized (this) {
                    if (session != generation) return;
                    socket = link;
                }
                link.setEnabledProtocols(new String[]{"TLSv1.2"}); link.setSoTimeout(10000); link.startHandshake();
                DataOutputStream out = new DataOutputStream(link.getOutputStream());
                DataInputStream input = new DataInputStream(link.getInputStream());
                out.writeUTF(token); out.flush();
                if (!input.readBoolean()) throw new IOException("접속 키가 올바르지 않습니다.");
                boolean allowed = input.readBoolean();
                synchronized (this) {
                    if (session != generation) return;
                    controlAllowed = allowed; output = out;
                }
                link.setSoTimeout(0);
                main.post(() -> { if (session == generation) {
                    health.connected(SystemClock.elapsedRealtime()); renderHealth();
                    status.setText(allowed ? "연결됨 · 화면 터치로 제어" : "연결됨 · 화면 보기 전용");
                    status.setText(deviceName + " · " + (allowed ? "화면 터치로 제어" : "화면 보기 전용"));
                    setViewMode(1);
                }});
                while (session == generation) {
                    int length = input.readInt();
                    if (length == Protocol.PONG) {
                        long echo = input.readLong();
                        boolean permission = input.readBoolean(), ready = input.readBoolean();
                        long received = SystemClock.elapsedRealtime();
                        main.post(() -> {
                            if (session == generation && health.pong(echo, received, permission, ready)) {
                                controlAllowed = permission && ready;
                                status.setText(!permission ? "연결됨 · 화면 보기 전용" : ready
                                        ? "연결됨 · 화면 터치로 제어" : "연결됨 · Target 터치 제어 권한 확인 필요");
                                renderHealth();
                            }
                        });
                        continue;
                    }
                    if (length <= 0 || length > Protocol.MAX_FRAME) throw new IOException("잘못된 화면 데이터");
                    byte[] bytes = new byte[length]; input.readFully(bytes);
                    if (pendingFrame.compareAndSet(false, true)) {
                        BitmapFactory.Options bounds = new BitmapFactory.Options(); bounds.inJustDecodeBounds = true;
                        BitmapFactory.decodeByteArray(bytes, 0, bytes.length, bounds);
                        if (bounds.outWidth <= 0 || bounds.outHeight <= 0 || bounds.outWidth > 1920 || bounds.outHeight > 1920) {
                            pendingFrame.set(false); throw new IOException("잘못된 화면 크기");
                        }
                        Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                        if (bitmap != null) bitmap.setDensity(Bitmap.DENSITY_NONE);
                        main.post(() -> {
                            pendingFrame.set(false);
                            if (session != generation || bitmap == null) { if (bitmap != null) bitmap.recycle(); return; }
                            current = bitmap; screen.setImageBitmap(bitmap); fitImage();
                            health.frame(); renderHealth();
                        });
                    }
                }
            } catch (Exception e) {
                String reason = e instanceof java.security.GeneralSecurityException || e instanceof javax.net.ssl.SSLException
                        ? "Target 인증 실패. 서버와 앱 설정을 확인하세요." : "연결 종료: " + (e instanceof IOException ? e.getMessage() : e.getClass().getSimpleName());
                main.post(() -> { if (session == generation) disconnect(reason); });
            } finally {
                if (link != null) try { link.close(); } catch (IOException ignored) {}
                if (upstream != null) try { upstream.close(); } catch (IOException ignored) {}
            }
        }, "host-network").start();
    }
    private void command(int kind, float x1, float y1, float x2, float y2, int duration) {
        final int session = generation;
        if (!controlAllowed || output == null || !health.canSendControl(SystemClock.elapsedRealtime())) return;
        commands.execute(() -> {
            DataOutputStream out = output;
            if (session != generation || out == null || !controlAllowed) return;
            try {
                out.writeByte(kind);
                if (kind == Protocol.GESTURE) {
                    out.writeFloat(x1); out.writeFloat(y1); out.writeFloat(x2); out.writeFloat(y2); out.writeInt(duration);
                }
                out.flush();
            } catch (IOException e) { main.post(() -> { if (session == generation) disconnect("제어 연결이 종료되었습니다."); }); }
        });
    }
    private void sendPing(long sent) {
        final int session = generation;
        health.sent(sent);
        commands.execute(() -> {
            DataOutputStream out = output;
            if (session != generation || out == null) return;
            try { out.writeByte(Protocol.PING); out.writeLong(sent); out.flush(); }
            catch (IOException e) { main.post(() -> { if (session == generation) disconnect("Target 상태 확인 연결이 종료되었습니다."); }); }
        });
    }
    private void renderHealth() {
        if (healthBar == null) return;
        long now = SystemClock.elapsedRealtime();
        ConnectionHealth.State state = health.state(now);
        int background, foreground = Color.WHITE;
        String label;
        switch (state) {
            case GOOD: background = Color.rgb(21, 110, 62); label = "● 연결 양호 · 제어 가능"; break;
            case VIEW_ONLY: background = Color.rgb(29, 78, 151); label = "● 연결 양호 · 화면 보기 전용"; break;
            case CONTROL_UNAVAILABLE: background = Color.rgb(255, 218, 128); foreground = Color.rgb(75, 48, 0); label = "● 제어 불가 · Target 권한 확인"; break;
            case DELAYED: background = Color.rgb(255, 218, 128); foreground = Color.rgb(75, 48, 0); label = "● 응답 지연 · 제어가 느릴 수 있음"; break;
            case UNRESPONSIVE: background = Color.rgb(174, 36, 36); label = "● Target 응답 없음"; break;
            case DISCONNECTED: background = Color.rgb(174, 36, 36); label = "● 연결 끊김 · 다시 연결 필요"; break;
            case CONNECTING: background = Color.rgb(255, 218, 128); foreground = Color.rgb(75, 48, 0); label = "● Target 연결 중…"; break;
            case CHECKING: background = Color.rgb(255, 218, 128); foreground = Color.rgb(75, 48, 0); label = "● Target 응답 / 화면 확인 중…"; break;
            default: background = Color.rgb(75, 85, 99); label = "● 연결 대기";
        }
        int level = health.qualityLevel(now);
        if (level >= 0 && state != ConnectionHealth.State.CHECKING && state != ConnectionHealth.State.CONTROL_UNAVAILABLE
                && state != ConnectionHealth.State.VIEW_ONLY) {
            background = QualityPalette.BACKGROUNDS[level]; foreground = QualityPalette.foreground(level);
            label = "● " + (state == ConnectionHealth.State.DISCONNECTED ? "연결 끊김" : QualityPalette.LABELS[level])
                    + " · 주의 단계 " + (level + 1) + "/10";
        }
        if (health.rtt() >= 0) {
            label += "\n최근 " + health.rtt() + "ms · 변동 " + (health.sampleCount() >= 2 ? health.jitter() + "ms" : "측정 중")
                    + " · 지연 응답 " + health.latePercent() + "% (" + health.sampleCount() + "회)";
            if (health.silence(now) >= ConnectionHealth.DELAY_MS)
                label += "\n응답 대기 " + String.format(java.util.Locale.KOREA, "%.1f초", health.silence(now) / 1000.0);
        }
        if (!label.contentEquals(healthBar.getText())) healthBar.setText(label);
        healthBar.setTextColor(foreground); healthBar.setBackgroundColor(background);
    }
    private void disconnect(String message) { disconnect(message, true); }
    private synchronized void disconnect(String message, boolean error) {
        generation++; controlAllowed = false; output = null; commands.getQueue().clear();
        health.disconnected(error); renderHealth();
        try { if (socket != null) socket.close(); } catch (IOException ignored) {}
        try { if (relay != null) relay.close(); } catch (IOException ignored) {}
        relay = null;
        socket = null; touching = false;
        if (screen != null) screen.setImageDrawable(null);
        current = null;
        if (status != null) status.setText(message);
        if (connect != null) connect.setEnabled(true);
        if (screen != null && healthBar != null) setViewMode(smallView ? 2 : 0);
    }
    @Override protected void onResume() { super.onResume(); main.removeCallbacks(healthTick); main.post(healthTick); main.removeCallbacks(listTick); main.post(listTick); }
    @Override protected void onPause() { main.removeCallbacks(healthTick); main.removeCallbacks(listTick); super.onPause(); }
    @Override protected void onStop() { disconnect("앱이 화면에서 벗어나 연결을 종료했습니다.", false); super.onStop(); }
    @Override public void onBackPressed() { if (fullScreen) setViewMode(0); else super.onBackPressed(); }
    @Override protected void onDestroy() {
        browsing = false; browseGeneration++; main.removeCallbacks(listTick);
        try { if (listing != null) listing.close(); } catch (IOException ignored) {} main.removeCallbacks(healthTick); disconnect("연결 종료", false); commands.shutdownNow(); super.onDestroy(); }
}
