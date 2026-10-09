package com.remotecontrol;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;
import java.io.IOException;
import java.util.UUID;
import javax.net.ssl.SSLSocket;

/** User-started relay presence, independent of screen capture permission. */
public final class ConnectionService extends Service {
    static volatile String status = "서버 연결 안 됨";
    static volatile boolean active;
    private volatile boolean running;
    private volatile SSLSocket socket;
    private Thread worker;
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public int onStartCommand(Intent intent, int flags, int id) {
        if (intent != null && "STOP".equals(intent.getAction())) {
            stopService(new Intent(this, CaptureService.class)); stopSelf(); return START_NOT_STICKY;
        }
        if (running) return START_NOT_STICKY;
        if (intent == null || !intent.hasExtra("host")) { stopSelf(); return START_NOT_STICKY; }
        getSystemService(NotificationManager.class).createNotificationChannel(
                new NotificationChannel("relay", "중계서버 연결 유지", NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 20, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop = PendingIntent.getService(this, 21, new Intent(this, ConnectionService.class).setAction("STOP"), PendingIntent.FLAG_IMMUTABLE);
        Notification notice = new Notification.Builder(this, "relay").setSmallIcon(android.R.drawable.ic_menu_view)
                .setContentTitle("RemoteControl 서버 연결 유지")
                .setContentText("인터넷 복구 시 자동 재접속 · 종료하려면 연결 종료")
                .setContentIntent(open).setOngoing(true)
                .addAction(new Notification.Action.Builder(null, "연결 종료", stop).build()).build();
        if (Build.VERSION.SDK_INT >= 34) startForeground(2, notice, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(2, notice);
        String host = intent.getStringExtra("host"); int port = intent.getIntExtra("port", Protocol.DEFAULT_RELAY_PORT);
        String deviceId = ServerSettings.deviceId(this);
        String secret = ServerSettings.secret(this);
        String deviceName = ServerSettings.preferences(this).getString("name", Build.MODEL);
        running = true; active = true;
        worker = new Thread(() -> {
            while (running) {
                status = "중계서버 접속 중…";
                try (SSLSocket connection = Relay.socket()) {
                    socket = connection;
                    if (!running) break;
                    Directory.open(connection, host, port, Directory.request("PRESENCE", secret, deviceId).put("name", deviceName).put("wake", true));
                    if (!running) break;
                    Diagnostics.record(this, "target", "relay presence connected", null);
                    status = "중계서버 연결됨 · 자동 재접속 사용 중";
                    connection.setSoTimeout(15000);
                    while (running) {
                        connection.getOutputStream().write("PING\n".getBytes(java.nio.charset.StandardCharsets.US_ASCII));
                        connection.getOutputStream().flush();
                        String response = Relay.line(connection);
                        if (response.matches("WAKE [0-9a-f]{32}")) {
                            String result = wakeScreen() ? "awake" : "blocked";
                            connection.getOutputStream().write(("WAKE_RESULT " + response.substring(5)
                                    + " " + result + "\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII));
                            connection.getOutputStream().flush();
                        } else if (!response.equals("PONG")) throw new IOException("서버 응답 오류");
                        Thread.sleep(10000);
                    }
                } catch (Exception error) {
                    if (running) {
                        Diagnostics.record(this, "target", "relay presence disconnected", error);
                        status = "중계서버 재접속 대기 · " + (error instanceof IOException ? error.getMessage() : error.getClass().getSimpleName());
                    }
                }
                if (!running) break;
                try { Thread.sleep(3000); } catch (InterruptedException stopped) { break; }
            }
        }, "relay-presence");
        worker.start();
        return START_NOT_STICKY;
    }
    // Bounded wake lock: no background Activity launch, unlock, or capture consent.
    @SuppressWarnings("deprecation")
    private boolean wakeScreen() throws InterruptedException {
        PowerManager power = getSystemService(PowerManager.class);
        PowerManager.WakeLock wake = null;
        try {
            if (!running || power == null) return false;
            if (power.isInteractive()) return true;
            wake = power.newWakeLock(PowerManager.SCREEN_BRIGHT_WAKE_LOCK
                    | PowerManager.ACQUIRE_CAUSES_WAKEUP, "RemoteControl:remoteWake");
            wake.acquire(3000);
            for (int i = 0; i < 10 && running && !power.isInteractive(); i++) Thread.sleep(100);
            boolean awake = running && power.isInteractive();
            Diagnostics.record(this, "target", "remote wake result=" + awake, null);
            return awake;
        } catch (RuntimeException error) {
            Diagnostics.record(this, "target", "remote wake blocked", error);
            return false;
        } finally {
            if (wake != null && wake.isHeld()) wake.release();
        }
    }
    @Override public void onDestroy() {
        running = false; active = false; status = "서버 연결 종료";
        Diagnostics.record(this, "target", "relay presence service stopped", null);
        if (worker != null) worker.interrupt();
        SSLSocket closingSocket = socket;
        if (closingSocket != null) {
            new Thread(() -> {
                try { closingSocket.close(); } catch (IOException ignored) {}
            }, "relay-presence-close").start();
        }
        stopForeground(STOP_FOREGROUND_REMOVE); super.onDestroy();
    }
}
