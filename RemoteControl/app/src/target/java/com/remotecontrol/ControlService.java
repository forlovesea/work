package com.remotecontrol;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.view.accessibility.AccessibilityEvent;

public final class ControlService extends AccessibilityService {
    static volatile ControlService instance;
    @Override protected void onServiceConnected() { instance = this; }
    @Override public void onAccessibilityEvent(AccessibilityEvent event) {}
    @Override public void onInterrupt() {}
    @Override public void onDestroy() { instance = null; super.onDestroy(); }
    static void command(int kind, float x1, float y1, float x2, float y2, int duration) {
        ControlService service = instance;
        CaptureService capture = CaptureService.instance;
        if (service == null || capture == null || !capture.canControl()) return;
        new android.os.Handler(android.os.Looper.getMainLooper()).post(() -> {
            if (!capture.canControl()) return;
            if (kind == Protocol.BACK) service.performGlobalAction(GLOBAL_ACTION_BACK);
            else if (kind == Protocol.HOME) service.performGlobalAction(GLOBAL_ACTION_HOME);
            else if (kind == Protocol.GESTURE && Protocol.coordinate(x1) && Protocol.coordinate(y1)
                    && Protocol.coordinate(x2) && Protocol.coordinate(y2) && duration >= 1 && duration <= 2000) {
                android.util.DisplayMetrics metrics = new android.util.DisplayMetrics();
                ((android.view.WindowManager) service.getSystemService(WINDOW_SERVICE)).getDefaultDisplay().getRealMetrics(metrics);
                // A rotation invalidates the image coordinates; wait for a new sharing session.
                if (metrics.widthPixels != capture.screenWidth || metrics.heightPixels != capture.screenHeight) return;
                Path path = new Path();
                path.moveTo(x1 * (metrics.widthPixels - 1), y1 * (metrics.heightPixels - 1));
                path.lineTo(x2 * (metrics.widthPixels - 1), y2 * (metrics.heightPixels - 1));
                service.dispatchGesture(new GestureDescription.Builder().addStroke(
                        new GestureDescription.StrokeDescription(path, 0, duration)).build(), null, null);
            }
        });
    }
}
