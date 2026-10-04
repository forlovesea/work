package com.remotecontrol;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.graphics.*;
import android.hardware.display.*;
import android.media.*;
import android.media.projection.*;
import android.os.*;
import android.util.DisplayMetrics;
import android.view.WindowManager;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import javax.net.ssl.*;

public final class CaptureService extends Service {
    static volatile CaptureService instance;
    static volatile String status = "공유를 시작하세요.", invitation = "";
    volatile int screenWidth, screenHeight;
    private volatile boolean running, connected, allowControl;
    private volatile SSLServerSocket server;
    private volatile SSLSocket client;
    private volatile SSLSocket relay;
    private String relayHost;
    private int relayPort;
    private volatile DataOutputStream output;
    private MediaProjection projection;
    private VirtualDisplay display;
    private ImageReader reader;
    private HandlerThread frames;
    private final Handler main = new Handler(Looper.getMainLooper());
    private long lastFrame;
    private String token;
    private final BroadcastReceiver screenOff = new BroadcastReceiver() {
        public void onReceive(Context c, Intent i) { finish("화면이 잠겨 공유를 중지했습니다."); }
    };
    boolean canControl() { return running && connected && allowControl; }
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public void onCreate() {
        super.onCreate(); instance = this;
        registerReceiver(screenOff, new IntentFilter(Intent.ACTION_SCREEN_OFF));
    }
    @Override public int onStartCommand(Intent intent, int flags, int id) {
        if (intent != null && "STOP".equals(intent.getAction())) { finish("공유를 중지했습니다."); return START_NOT_STICKY; }
        if (running) return START_NOT_STICKY;
        NotificationManager notifications = getSystemService(NotificationManager.class);
        notifications.createNotificationChannel(new NotificationChannel("sharing", "원격 화면 공유", NotificationManager.IMPORTANCE_LOW));
        PendingIntent stop = PendingIntent.getService(this, 0, new Intent(this, CaptureService.class).setAction("STOP"), PendingIntent.FLAG_IMMUTABLE);
        PendingIntent open = PendingIntent.getActivity(this, 1, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification notice = new Notification.Builder(this, "sharing").setSmallIcon(android.R.drawable.ic_menu_view)
                .setContentTitle("RemoteControl 화면 공유 중").setContentText("누르면 앱 열기 · 중지 버튼으로 접속 차단")
                .setOngoing(true).setContentIntent(open).addAction(new Notification.Action.Builder(null, "공유 중지", stop).build()).build();
        if (Build.VERSION.SDK_INT >= 29) startForeground(1, notice, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        else startForeground(1, notice);
        if (intent == null || !intent.hasExtra("data")) { finish("공유 권한이 필요합니다."); return START_NOT_STICKY; }
        running = true; status = "보안 연결 준비 중…"; allowControl = intent.getBooleanExtra("control", false);
        relayHost = intent.getStringExtra("relayHost"); relayPort = intent.getIntExtra("relayPort", Protocol.DEFAULT_RELAY_PORT);
        try {
            MediaProjectionManager manager = (MediaProjectionManager) getSystemService(MEDIA_PROJECTION_SERVICE);
            projection = manager.getMediaProjection(intent.getIntExtra("result", 0), intent.getParcelableExtra("data"));
            projection.registerCallback(new MediaProjection.Callback() {
                @Override public void onStop() { finish("시스템에서 화면 공유를 종료했습니다."); }
                @Override public void onCapturedContentResize(int w, int h) {
                    if (w != screenWidth || h != screenHeight) finish("화면 크기가 변경되었습니다. 공유를 다시 시작하세요.");
                }
            }, main);
            DisplayMetrics metrics = new DisplayMetrics();
            ((WindowManager) getSystemService(WINDOW_SERVICE)).getDefaultDisplay().getRealMetrics(metrics);
            screenWidth = metrics.widthPixels; screenHeight = metrics.heightPixels;
            float scale = Math.min(1f, 960f / Math.max(screenWidth, screenHeight));
            int width = Math.max(1, Math.round(screenWidth * scale)), height = Math.max(1, Math.round(screenHeight * scale));
            frames = new HandlerThread("screen-frames"); frames.start();
            reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2);
            reader.setOnImageAvailableListener(this::sendFrame, new Handler(frames.getLooper()));
            display = projection.createVirtualDisplay("RemoteControl", width, height, metrics.densityDpi,
                    DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, reader.getSurface(), null, main);
            byte[] random = new byte[16]; new SecureRandom().nextBytes(random);
            StringBuilder secret = new StringBuilder();
            for (byte b : random) secret.append(String.format(Locale.ROOT, "%02x", b & 255));
            token = secret.toString();
            new Thread(this::serve, "target-network").start();
            main.postDelayed(() -> finish("30분 세션 시간이 만료되었습니다."), 30 * 60 * 1000L);
        } catch (Exception e) { finish("공유 시작 실패: " + e.getClass().getSimpleName()); }
        return START_NOT_STICKY;
    }
    private void serve() {
        try {
            Identity identity = new Identity();
            SSLServerSocket listener = (SSLServerSocket) identity.context.getServerSocketFactory().createServerSocket();
            server = listener;
            if (!running) { listener.close(); return; }
            listener.bind(new InetSocketAddress("127.0.0.1", 0));
            listener.setEnabledProtocols(new String[]{"TLSv1.2"});
            String room = UUID.randomUUID().toString().replace("-", "");
            SSLSocket upstream = Relay.socket(); relay = upstream;
            if (!running) { upstream.close(); return; }
            Relay.register(upstream, relayHost, relayPort, "TARGET", room);
            if (!running) return;
            invitation = "RC2|" + relayHost + "|" + relayPort + "|" + room + "|" + identity.fingerprint + "|" + token + "|" + Protocol.WIRE_VERSION;
            status = "중계서버 연결됨 · Host 연결 대기";
            upstream.setSoTimeout(5 * 60 * 1000);
            if (!Relay.line(upstream).equals("PAIRED")) throw new IOException("Relay pairing failed");
            upstream.setSoTimeout(0);
            Socket local = new Socket("127.0.0.1", listener.getLocalPort());
            Relay.bridge(upstream, local);
            while (running && !connected) {
                SSLSocket socket = (SSLSocket) listener.accept(); client = socket;
                if (!running) { socket.close(); return; }
                try {
                    socket.setSoTimeout(10000); socket.startHandshake();
                    DataInputStream input = new DataInputStream(socket.getInputStream());
                    DataOutputStream out = new DataOutputStream(socket.getOutputStream());
                    String supplied = input.readUTF();
                    boolean match = MessageDigest.isEqual(token.getBytes(StandardCharsets.US_ASCII), supplied.getBytes(StandardCharsets.US_ASCII));
                    out.writeBoolean(match); out.flush();
                    if (!match) { socket.close(); finish("접속 인증 실패. 새 공유 세션을 시작하세요."); return; }
                    out.writeBoolean(allowControl); out.flush();
                    connected = true; invitation = ""; output = out;
                    listener.close(); socket.setSoTimeout(0);
                    status = allowControl ? "Host 연결됨 · 화면 공유 및 터치 제어 중" : "Host 연결됨 · 화면 보기 전용";
                    long lastCommand = 0;
                    while (running) {
                        int kind = input.readUnsignedByte();
                        if (kind == Protocol.PING) {
                            long echo = input.readLong();
                            // Check the Target main thread as well as the end-to-end network path.
                            java.util.concurrent.CompletableFuture<Boolean> readiness = new java.util.concurrent.CompletableFuture<>();
                            main.post(() -> readiness.complete(canControl() && ControlService.instance != null));
                            boolean ready = readiness.get(5, java.util.concurrent.TimeUnit.SECONDS);
                            synchronized (out) {
                                out.writeInt(Protocol.PONG); out.writeLong(echo);
                                out.writeBoolean(allowControl); out.writeBoolean(ready); out.flush();
                            }
                            continue;
                        }
                        float x1 = 0, y1 = 0, x2 = 0, y2 = 0; int duration = 1;
                        if (kind == Protocol.GESTURE) {
                            x1 = input.readFloat(); y1 = input.readFloat(); x2 = input.readFloat(); y2 = input.readFloat(); duration = input.readInt();
                        } else if (kind != Protocol.BACK && kind != Protocol.HOME) throw new IOException("invalid command");
                        long now = SystemClock.elapsedRealtime();
                        if (now - lastCommand >= 60) { ControlService.command(kind, x1, y1, x2, y2, duration); lastCommand = now; }
                    }
                } catch (IOException e) {
                    socket.close();
                    finish("Host 연결이 종료되었습니다."); return;
                }
            }
        } catch (Exception e) { if (running) finish("연결 종료: " + e.getClass().getSimpleName()); }
    }
    private void sendFrame(ImageReader source) {
        try (Image image = source.acquireLatestImage()) {
            if (image == null || !running || !connected || output == null) return;
            long now = SystemClock.elapsedRealtime();
            if (now - lastFrame < 200) return;
            lastFrame = now;
            Image.Plane plane = image.getPlanes()[0];
            int paddedWidth = plane.getRowStride() / plane.getPixelStride();
            Bitmap padded = Bitmap.createBitmap(paddedWidth, image.getHeight(), Bitmap.Config.ARGB_8888);
            padded.copyPixelsFromBuffer(plane.getBuffer());
            Bitmap cropped = Bitmap.createBitmap(padded, 0, 0, image.getWidth(), image.getHeight());
            ByteArrayOutputStream bytes = new ByteArrayOutputStream(); cropped.compress(Bitmap.CompressFormat.JPEG, 60, bytes);
            if (cropped != padded) cropped.recycle(); padded.recycle();
            if (bytes.size() > Protocol.MAX_FRAME) return;
            DataOutputStream out = output;
            if (out != null && running) {
                synchronized (out) { out.writeInt(bytes.size()); bytes.writeTo(out); out.flush(); }
            }
        } catch (Exception e) { if (running) finish("화면 전송이 종료되었습니다."); }
    }
    private void finish(String message) {
        if (!running) { stopSelf(); return; }
        status = message; running = false; connected = false; invitation = "";
        main.post(this::stopSelf);
    }
    @Override public void onConfigurationChanged(android.content.res.Configuration configuration) {
        super.onConfigurationChanged(configuration);
        DisplayMetrics metrics = new DisplayMetrics();
        ((WindowManager) getSystemService(WINDOW_SERVICE)).getDefaultDisplay().getRealMetrics(metrics);
        if (running && (metrics.widthPixels != screenWidth || metrics.heightPixels != screenHeight))
            finish("화면이 회전되었습니다. 공유를 다시 시작하세요.");
    }
    @Override public void onDestroy() {
        running = false; connected = false; allowControl = false; invitation = ""; output = null;
        main.removeCallbacksAndMessages(null);
        try { if (server != null) server.close(); } catch (IOException ignored) {}
        try { if (client != null) client.close(); } catch (IOException ignored) {}
        try { if (relay != null) relay.close(); } catch (IOException ignored) {}
        if (display != null) display.release();
        if (reader != null) reader.close();
        if (projection != null) projection.stop();
        if (frames != null) frames.quitSafely();
        unregisterReceiver(screenOff); instance = null;
        if (status.startsWith("Host") || status.startsWith("보안")) status = "공유를 중지했습니다.";
        stopForeground(STOP_FOREGROUND_REMOVE); super.onDestroy();
    }
}
