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
    private Thread networkThread;
    private String room;
    private boolean frameErrorLogged;
    private boolean firstFrameSent;
    private volatile long lastIncoming;
    private PowerManager.WakeLock screenLease;
    private final Runnable connectionWatch = new Runnable() {
        @Override public void run() {
            if (!running) return;
            if (connected && SystemClock.elapsedRealtime() - lastIncoming > 20000) closeConnections();
            main.postDelayed(this, 2000);
        }
    };
    boolean canControl() { return running && connected && allowControl; }
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public void onCreate() {
        super.onCreate(); instance = this;
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
        Diagnostics.record(this, "target", "screen sharing service started", null);
        relayHost = intent.getStringExtra("relayHost"); relayPort = intent.getIntExtra("relayPort", Protocol.DEFAULT_RELAY_PORT);
        try {
            MediaProjectionManager manager = (MediaProjectionManager) getSystemService(MEDIA_PROJECTION_SERVICE);
            projection = manager.getMediaProjection(intent.getIntExtra("result", 0), intent.getParcelableExtra("data"));
            projection.registerCallback(new MediaProjection.Callback() {
                @Override public void onStop() {
                    Diagnostics.record(CaptureService.this, "target", "system revoked screen capture; relay presence remains independent", null);
                    finish("시스템이 화면 공유를 중지했습니다. 중계서버 연결은 유지됩니다. 잠금 해제 후 화면 공유를 다시 시작하세요.");
                }
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
            Diagnostics.record(this, "target", "screen capture initialized: " + width + "x" + height
                    + " source=" + screenWidth + "x" + screenHeight, null);
            byte[] random = new byte[16]; new SecureRandom().nextBytes(random);
            StringBuilder secret = new StringBuilder();
            for (byte b : random) secret.append(String.format(Locale.ROOT, "%02x", b & 255));
            token = secret.toString();
            room = UUID.randomUUID().toString().replace("-", "");
            networkThread = new Thread(this::serve, "target-network");
            networkThread.start();
            main.post(connectionWatch);
        } catch (Exception e) {
            Diagnostics.record(this, "target", "screen sharing setup failed", e);
            finish("공유 시작 실패: " + e.getClass().getSimpleName());
        }
        return START_NOT_STICKY;
    }
    private void serve() {
        while (running) {
            status = "보안 연결 준비 중…";
            serveOnce();
            boolean used = connected;
            connected = false; output = null;
            closeConnections();
            if (!running) break;
            if (used) {
                room = UUID.randomUUID().toString().replace("-", "");
                token = UUID.randomUUID().toString().replace("-", "");
            }
            invitation = "";
            if (!status.startsWith("Target TLS 핸드셰이크 실패: ")
                    && !status.startsWith("Target 보안 연결 실패: ")
                    && !status.startsWith("화면 프레임 생성 실패 ")
                    && !status.startsWith("화면 전송 연결 종료: ")) {
                status = "중계서버 재접속 대기 · 인터넷 복구 시 자동 연결";
            }
            try { Thread.sleep(3000); }
            catch (InterruptedException stopped) { break; }
        }
    }
    // Renewed by authenticated Host heartbeats; expires even if the network stalls.
    @SuppressWarnings("deprecation")
    private synchronized void keepScreenAwake(boolean enabled) {
        if (!enabled || !running || !connected) { releaseScreenLease(); return; }
        PowerManager power = getSystemService(PowerManager.class);
        if (power == null || !power.isInteractive()) { releaseScreenLease(); return; }
        try {
            if (screenLease == null) {
                screenLease = power.newWakeLock(PowerManager.SCREEN_BRIGHT_WAKE_LOCK, "RemoteControl:screenLease");
                screenLease.setReferenceCounted(false);
            }
            screenLease.acquire(15000);
        } catch (RuntimeException error) {
            releaseScreenLease();
            Diagnostics.record(this, "target", "screen keep-awake failed", error);
        }
    }
    private synchronized void releaseScreenLease() {
        if (screenLease != null && screenLease.isHeld()) screenLease.release();
        screenLease = null;
    }
    private void closeConnections() {
        releaseScreenLease();
        Diagnostics.record(this, "target", "application closing connections running=" + running + " connected=" + connected, null);
        SSLServerSocket closingServer = server;
        SSLSocket closingClient = client;
        SSLSocket closingRelay = relay;
        Thread closer = new Thread(() -> {
            try { if (closingServer != null) closingServer.close(); } catch (IOException ignored) {}
            try { if (closingClient != null) closingClient.close(); } catch (IOException ignored) {}
            try { if (closingRelay != null) closingRelay.close(); } catch (IOException ignored) {}
        }, "target-close");
        closer.start();
    }
    private void serveOnce() {
        String stage = "Target identity initialization";
        try {
            Identity identity = new Identity(this);
            stage = "local TLS listener setup";
            SSLServerSocket listener = (SSLServerSocket) identity.context.getServerSocketFactory().createServerSocket();
            server = listener;
            if (!running) { listener.close(); return; }
            listener.bind(new InetSocketAddress("127.0.0.1", 0));
            Tls.configure(listener, "EC");
            Diagnostics.record(this, "target", "Target identity ready: ECDSA certificate", null);
            stage = "relay SHARE registration";
            SSLSocket upstream = Relay.socket(); relay = upstream;
            if (!running) { upstream.close(); return; }
            Directory.open(upstream, relayHost, relayPort,
                    Directory.request("SHARE", ServerSettings.secret(this), ServerSettings.deviceId(this))
                            .put("fingerprint", identity.fingerprint).put("token", token));
            if (!running) return;
            Diagnostics.record(this, "target", "relay accepted SHARE registration", null);
            invitation = "";
            status = "중계서버 연결됨 · Host 연결 대기";
            upstream.setSoTimeout(60000);
            if (!Relay.line(upstream).equals("PAIRED")) throw new IOException("Relay pairing failed");
            Diagnostics.record(this, "target", "relay paired Host session", null);
            upstream.setSoTimeout(0);
            Socket local = new Socket("127.0.0.1", listener.getLocalPort());
            Relay.bridge(upstream, local, (event, error) -> Diagnostics.record(this, "target", event, error));
            while (running && !connected) {
                SSLSocket socket = (SSLSocket) listener.accept(); client = socket;
                if (!running) { socket.close(); return; }
                boolean handshakeComplete = false;
                try {
                    stage = "Target TLS handshake";
                    socket.setSoTimeout(30000); Tls.configure(socket, "EC");
                    Diagnostics.record(this, "target", "TLS handshake starting clientMode=" + socket.getUseClientMode()
                            + " protocols=" + Arrays.toString(socket.getEnabledProtocols()), null);
                    Diagnostics.record(this, "target", "TLS enabled suites=" + Arrays.toString(socket.getEnabledCipherSuites()), null);
                    socket.startHandshake();
                    handshakeComplete = true;
                    Diagnostics.record(this, "target", "Host TLS handshake completed: "
                            + socket.getSession().getProtocol() + " " + socket.getSession().getCipherSuite(), null);
                    DataInputStream input = new DataInputStream(socket.getInputStream());
                    DataOutputStream out = new DataOutputStream(socket.getOutputStream());
                    String supplied = input.readUTF();
                    boolean match = MessageDigest.isEqual(token.getBytes(StandardCharsets.US_ASCII), supplied.getBytes(StandardCharsets.US_ASCII));
                    out.writeBoolean(match); out.flush();
                    if (!match) { socket.close(); finish("접속 인증 실패. 새 공유 세션을 시작하세요."); return; }
                    out.writeBoolean(allowControl); out.flush();
                    Diagnostics.record(this, "target", "Host session token accepted", null);
                    lastIncoming = SystemClock.elapsedRealtime();
                    connected = true; invitation = ""; output = out;
                    listener.close(); socket.setSoTimeout(15000);
                    status = allowControl ? "Host 연결됨 · 화면 공유 및 터치 제어 중" : "Host 연결됨 · 화면 보기 전용";
                    long lastCommand = 0;
                    while (running) {
                        int kind = input.readUnsignedByte();
                        lastIncoming = SystemClock.elapsedRealtime();
                        if (kind == Protocol.KEEP_AWAKE) {
                            keepScreenAwake(input.readBoolean());
                            continue;
                        }
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
                    if (!status.startsWith("화면 전송 연결 종료: ")) {
                        Diagnostics.record(this, "target", handshakeComplete
                                ? "Host session ended"
                                : "TLS handshake failed; suites=" + Arrays.toString(socket.getEnabledCipherSuites()), e);
                        status = handshakeComplete
                                ? "Host 연결 종료: " + failureDetail(e)
                                : "Target TLS 핸드셰이크 실패: " + failureDetail(e);
                    }
                    socket.close();
                    return;
                }
            }
        } catch (Exception e) {
            if (running) {
                Diagnostics.record(this, "target", "screen sharing failed at " + stage, e);
                status = "Target 보안 연결 실패: " + failureDetail(e);
            }
        }
    }
    private static String failureDetail(Throwable error) {
        for (Throwable cause = error; cause != null; cause = cause.getCause()) {
            String message = cause.getMessage();
            if (message != null && !message.trim().isEmpty()) return message;
        }
        return error.getClass().getSimpleName();
    }
    private void sendFrame(ImageReader source) {
        SSLSocket sendingClient = client;
        DataOutputStream sendingOutput = output;
        Bitmap bitmap = null;
        byte[] frame;
        int frameWidth = 0, frameHeight = 0;
        try (Image image = source.acquireLatestImage()) {
            if (image == null || !running || !connected || output == null) return;
            long now = SystemClock.elapsedRealtime();
            if (now - lastFrame < 200) return;
            lastFrame = now;
            Image.Plane plane = image.getPlanes()[0];
            int width = image.getWidth(), height = image.getHeight();
            frameWidth = width;
            frameHeight = height;
            byte[] compact = FramePixels.compactRgba(plane.getBuffer().duplicate(), width, height,
                    plane.getRowStride(), plane.getPixelStride());
            bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
            bitmap.copyPixelsFromBuffer(java.nio.ByteBuffer.wrap(compact));
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 60, bytes)) {
                throw new IOException("JPEG 화면 프레임 인코딩 실패");
            }
            frame = bytes.toByteArray();
            if (frame.length == 0 || frame.length > Protocol.MAX_FRAME) {
                throw new IOException("화면 프레임 크기가 허용 범위를 벗어났습니다.");
            }
        } catch (Exception e) {
            if (running && connected) {
                status = "화면 프레임 생성 실패 (연결 유지): " + failureDetail(e);
                if (!frameErrorLogged) {
                    Diagnostics.record(this, "target", "screen frame creation failed; session kept alive", e);
                    frameErrorLogged = true;
                }
            }
            return;
        } finally {
            if (bitmap != null) bitmap.recycle();
        }
        DataOutputStream out = sendingOutput;
        if (out == null || !running || !connected || out != output) return;
        try {
            synchronized (out) {
                out.writeInt(frame.length);
                out.write(frame);
                out.flush();
            }
            if (status.startsWith("화면 프레임 생성 실패 ")) {
                status = allowControl ? "Host 연결됨 · 화면 공유 및 터치 제어 중"
                        : "Host 연결됨 · 화면 보기 전용";
            }
            if (!firstFrameSent) {
                Diagnostics.record(this, "target", "first screen frame sent: " + frameWidth + "x" + frameHeight, null);
                firstFrameSent = true;
            }
            frameErrorLogged = false;
        } catch (IOException e) {
            if (running && connected) status = "화면 전송 연결 종료: " + failureDetail(e);
            Diagnostics.record(this, "target", "screen frame write failed", e);
            try { if (sendingClient != null) sendingClient.close(); } catch (IOException ignored) {}
        }
    }
    private void finish(String message) {
        if (!running) { stopSelf(); return; }
        status = message; running = false; connected = false; invitation = "";
        releaseScreenLease();
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
        if (networkThread != null) networkThread.interrupt();
        main.removeCallbacksAndMessages(null);
        closeConnections();
        if (display != null) display.release();
        if (reader != null) reader.close();
        if (projection != null) projection.stop();
        if (frames != null) frames.quitSafely();
        instance = null;
        Diagnostics.record(this, "target", "screen sharing service stopped: " + status, null);
        if (status.startsWith("Host") || status.startsWith("보안")) status = "공유를 중지했습니다.";
        stopForeground(STOP_FOREGROUND_REMOVE); super.onDestroy();
    }
}
