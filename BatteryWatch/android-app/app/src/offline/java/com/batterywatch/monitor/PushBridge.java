package com.batterywatch.monitor;
import android.app.Activity;
import android.content.Context;
final class PushBridge {
    static final Object LOCK = new Object();
    static void initialize(Activity activity) {}
    static void unregister(Context context) {}
    static String description(Context context) { return "조회 전용 빌드: 백그라운드 푸시 알림 미지원"; }
}
