package com.batterywatch.monitor;

import android.Manifest;
import android.app.*;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import com.google.firebase.messaging.FirebaseMessaging;
import org.json.JSONObject;
import java.util.UUID;

final class PushBridge {
    static final Object LOCK = new Object();
    static void initialize(Activity activity) {
        NotificationManager manager = activity.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("battery_alarms", "축전지 알람", NotificationManager.IMPORTANCE_HIGH));
        if (Build.VERSION.SDK_INT >= 33 && activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            activity.requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 10);
        FirebaseMessaging.getInstance().getToken().addOnSuccessListener(token -> register(activity.getApplicationContext(), token));
    }
    static String installation(Context context) {
        android.content.SharedPreferences prefs = context.getSharedPreferences("push", Context.MODE_PRIVATE);
        String id = prefs.getString("installation", "");
        if (id.isEmpty()) { id = UUID.randomUUID().toString(); if (!prefs.edit().putString("installation", id).commit()) throw new IllegalStateException("설정 저장 실패"); }
        return id;
    }
    static void register(Context context, String token) {
        new Thread(() -> {
            synchronized (LOCK) {
                SettingsStore settings = new SettingsStore(context);
                if (settings.url().isEmpty()) return;
                try {
                    new ApiClient(settings.url(), settings.token()).request("PUT", "/api/v1/push-devices/" + installation(context), new JSONObject().put("token", token));
                    context.getSharedPreferences("push", Context.MODE_PRIVATE).edit().putString("status", "푸시 등록 완료").apply();
                } catch (Exception e) {
                    context.getSharedPreferences("push", Context.MODE_PRIVATE).edit().putString("status", "푸시 등록 실패 — 앱 재실행 시 재시도").apply();
                }
            }
        }, "push-registration").start();
    }
    static void unregister(Context context) throws Exception {
        synchronized (LOCK) {
            SettingsStore settings = new SettingsStore(context);
            if (settings.url().isEmpty()) return;
            new ApiClient(settings.url(), settings.token()).request("DELETE", "/api/v1/push-devices/" + installation(context), new JSONObject());
            com.google.android.gms.tasks.Tasks.await(FirebaseMessaging.getInstance().deleteToken(), 10, java.util.concurrent.TimeUnit.SECONDS);
            context.getSharedPreferences("push", Context.MODE_PRIVATE).edit().remove("status").apply();
        }
    }
    static String description(Context context) {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        return manager.areNotificationsEnabled() ? context.getSharedPreferences("push", Context.MODE_PRIVATE).getString("status", "푸시 등록 대기") : "알림 권한이 꺼져 있습니다. Android 설정에서 허용하세요.";
    }
}
