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
    private EditText invitation;
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
        LinearLayout page = Ui.page(this, "Host · 접속하는 기기");
        Ui.text(this, page, "Target의 접속 정보를 붙여 넣으세요. LTE / Wi-Fi에서 중계서버를 통해 연결합니다.");
        invitation = new EditText(this); invitation.setHint("Target에서 복사한 최신 접속 정보");
        invitation.setSingleLine(true); invitation.setTextSize(12);
        invitation.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
        page.addView(invitation);
        connect = Ui.button(this, page, "Target 연결", v -> connect());
        Ui.button(this, page, "연결 종료", v -> disconnect("연결을 종료했습니다.", false));
        status = Ui.text(this, page, "대기 중");
        LinearLayout navigation = new LinearLayout(this); page.addView(navigation);
        Ui.button(this, navigation, "뒤로", v -> command(Protocol.BACK, 0, 0, 0, 0, 1));
        Ui.button(this, navigation, "홈", v -> command(Protocol.HOME, 0, 0, 0, 0, 1));
        screen = new ImageView(this); screen.setBackgroundColor(Color.rgb(15, 23, 42));
        screen.setScaleType(ImageView.ScaleType.FIT_CENTER);
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
    private void connect() {
        final String[] info;
        try { info = Protocol.invitation(invitation.getText().toString()); }
        catch (IllegalArgumentException e) { status.setText(e.getMessage()); return; }
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
                Relay.register(upstream, info[1], Integer.parseInt(info[2]), "HOST", info[3]);
                upstream.setSoTimeout(0);
                Socket tunnel = Relay.localTunnel(upstream);
                try { link = (SSLSocket) Tls.client(info[4]).getSocketFactory().createSocket(tunnel, "target", 0, true); }
                catch (Exception e) { tunnel.close(); throw e; }
                synchronized (this) {
                    if (session != generation) return;
                    socket = link;
                }
                link.setEnabledProtocols(new String[]{"TLSv1.2"}); link.setSoTimeout(10000); link.startHandshake();
                DataOutputStream out = new DataOutputStream(link.getOutputStream());
                DataInputStream input = new DataInputStream(link.getInputStream());
                out.writeUTF(info[5]); out.flush();
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
                    invitation.setText("");
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
                            current = bitmap; screen.setImageBitmap(bitmap);
                            health.frame(); renderHealth();
                        });
                    }
                }
            } catch (Exception e) {
                String reason = e instanceof java.security.GeneralSecurityException || e instanceof javax.net.ssl.SSLException
                        ? "Target 인증 실패. 접속 정보를 다시 확인하세요." : "연결 종료: " + e.getClass().getSimpleName();
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
    }
    @Override protected void onResume() { super.onResume(); main.removeCallbacks(healthTick); main.post(healthTick); }
    @Override protected void onPause() { main.removeCallbacks(healthTick); super.onPause(); }
    @Override protected void onStop() { disconnect("앱이 화면에서 벗어나 연결을 종료했습니다.", false); super.onStop(); }
    @Override protected void onDestroy() { main.removeCallbacks(healthTick); disconnect("연결 종료", false); commands.shutdownNow(); super.onDestroy(); }
}
