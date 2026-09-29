package com.batterywatch.monitor;

import android.app.*;
import android.content.Intent;
import android.content.Context;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;
import java.util.Map;

public class AlarmMessagingService extends FirebaseMessagingService {
    @Override public void onNewToken(String token) { PushBridge.register(this, token); }
    @Override public void onMessageReceived(RemoteMessage message) {
        Map<String, String> data = message.getData();
        String id = data.get("event_id"); if (id == null) return;
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("battery_alarms", "축전지 알람", NotificationManager.IMPORTANCE_HIGH));
        if (!manager.areNotificationsEnabled()) return;
        Intent intent = new Intent(this, MainActivity.class).putExtra("site_id", data.get("site_id")).putExtra("device_id", data.get("device_id"));
        PendingIntent pending = PendingIntent.getActivity(this, id.hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new Notification.Builder(this, "battery_alarms")
            .setSmallIcon(R.drawable.ic_battery).setContentTitle(data.get("site_id") + "/" + data.get("device_id") + ": " + data.get("transition"))
            .setContentText(data.get("message")).setStyle(new Notification.BigTextStyle().bigText(data.get("message")))
            .setContentIntent(pending).setAutoCancel(true).build();
        manager.notify(id, 0, notification);
    }
}
