package com.batterywatch.monitor;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.graphics.Color;
import android.text.InputType;
import android.view.View;
import android.widget.*;
import org.json.*;
import java.util.Iterator;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Foreground polling only; background alerts are delivered by FCM. */
public class MainActivity extends Activity {
    private SettingsStore settings;
    private LinearLayout content;
    private TextView status;
    private BatteryDashboard dashboard;
    private ScrollView scroll;
    private ConnectionSettingsDialog settingsDialog;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private boolean resumed, busy, closing;
    private int generation;
    private String site = "", device = "", page = "devices";
    private final Runnable poll = new Runnable() {
        @Override public void run() {
            if (!resumed) return;
            refresh();
            handler.postDelayed(this, Math.max(5, settings.interval()) * 1000L);
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        settings = new SettingsStore(this);
        dashboard = new BatteryDashboard(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dashboard.dp(16), dashboard.dp(12), dashboard.dp(16), dashboard.dp(8));
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            root.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(android.view.WindowInsets.Type.systemBars());
                view.setPadding(dashboard.dp(16) + bars.left, dashboard.dp(12) + bars.top, dashboard.dp(16) + bars.right, dashboard.dp(8) + bars.bottom);
                return insets;
            });
        }
        root.setBackgroundColor(BatteryDashboard.BG);
        TextView title = new TextView(this);
        title.setText("BatteryWatch"); title.setTextSize(26); title.setTextColor(BatteryDashboard.INK);
        LinearLayout header = new LinearLayout(this);
        header.setGravity(android.view.Gravity.CENTER_VERTICAL);
        header.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button exit = new Button(this);
        exit.setText("종료"); exit.setAllCaps(false);
        exit.setTextColor(BatteryDashboard.AMBER);
        exit.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(30, 48, 62)));
        exit.setOnClickListener(v -> exitApp());
        header.addView(exit, new LinearLayout.LayoutParams(dashboard.dp(80), dashboard.dp(48)));
        root.addView(header);
        LinearLayout actions = new LinearLayout(this);
        button(actions, "장비", () -> navigate("devices"));
        button(actions, "설정", this::showSettings);
        button(actions, "새로고침", this::refresh);
        root.addView(actions);
        status = new TextView(this); status.setTextSize(12); status.setTextColor(BatteryDashboard.MUTED); status.setPadding(0, dashboard.dp(10), 0, dashboard.dp(10)); root.addView(status);
        scroll = new ScrollView(this);
        content = new LinearLayout(this); content.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(content); root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        PushBridge.initialize(this);
        if (getIntent().hasExtra("site_id")) {
            site = getIntent().getStringExtra("site_id"); device = getIntent().getStringExtra("device_id"); page = "alarms";
        }
    }

    @Override protected void onResume() { super.onResume(); resumed = true; handler.post(poll); }
    @Override protected void onPause() { resumed = false; handler.removeCallbacks(poll); super.onPause(); }
    @Override protected void onDestroy() { resumed = false; generation++; if (settingsDialog != null) settingsDialog.dismiss(); handler.removeCallbacksAndMessages(null); network.shutdownNow(); super.onDestroy(); }

    private void exitApp() {
        if (closing) return;
        closing = true;
        resumed = false;
        generation++;
        handler.removeCallbacksAndMessages(null);
        if (settingsDialog != null) settingsDialog.dismiss();
        network.shutdownNow();
        finishAndRemoveTask();
    }

    private void button(LinearLayout parent, String label, Runnable action) {
        Button b = new Button(this); b.setText(label); b.setAllCaps(false); b.setTextColor(BatteryDashboard.GREEN); b.setTextSize(13);
        b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(30, 48, 62)));
        b.setOnClickListener(v -> action.run());
        parent.addView(b, new LinearLayout.LayoutParams(parent.getOrientation() == LinearLayout.HORIZONTAL ? 0 : -1, dashboard.dp(48), parent.getOrientation() == LinearLayout.HORIZONTAL ? 1 : 0));
    }

    private void text(String value, boolean heading) {
        TextView view = new TextView(this); view.setText(value); view.setTextSize(heading ? 20 : 16);
        view.setTextColor(heading ? BatteryDashboard.INK : BatteryDashboard.MUTED); view.setPadding(6, 12, 6, 12); content.addView(view);
    }

    private void navigate(String next) { page = next; generation++; content.removeAllViews(); scroll.scrollTo(0, 0); refresh(); }

    private void refresh() {
        if (closing || network.isShutdown() || busy || isFinishing() || (settingsDialog != null && settingsDialog.isShowing())) return;
        if (settings.url().isEmpty()) { status.setText("서버 연결 대기"); status.setTextColor(BatteryDashboard.MUTED); content.setAlpha(1f); content.removeAllViews(); dashboard.empty(content, this::showSettings); return; }
        busy = true;
        final int requestGeneration = generation;
        final String requestedPage = page;
        final String selectedSite = site, selectedDevice = device;
        status.setText("서버 조회 중…");
        network.execute(() -> {
            try {
                ApiClient api = new ApiClient(settings.url(), settings.token());
                String path = requestedPage.equals("devices") ? "/api/v1/devices" :
                    "/api/v1/" + (requestedPage.equals("details") ? "snapshot" : requestedPage) + ApiClient.query(selectedSite, selectedDevice);
                JSONObject response = api.get(path);
                runOnUiThread(() -> {
                    busy = false;
                    if (closing || isFinishing() || isDestroyed()) return;
                    if (requestGeneration != generation) { refresh(); return; }
                    try { int y = scroll.getScrollY(); render(requestedPage, response); scroll.post(() -> scroll.scrollTo(0, y)); }
                    catch (Exception e) { status.setText("서버 데이터 형식을 확인하세요."); }
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    busy = false;
                    if (closing || isFinishing() || isDestroyed()) return;
                    if (requestGeneration != generation) { refresh(); return; }
                    status.setText("조회 실패 — 표시된 값은 이전 데이터입니다.\n" + e.getMessage());
                    status.setTextColor(BatteryDashboard.AMBER); content.setAlpha(0.55f);
                });
            }
        });
    }

    private void render(String requestedPage, JSONObject response) throws JSONException {
        content.removeAllViews(); content.setAlpha(1f); status.setTextColor(BatteryDashboard.MUTED);
        status.setText("서버 응답: " + response.optString("server_time", ""));
        if (requestedPage.equals("devices")) {
            JSONArray devices = response.getJSONArray("devices");
            if (devices.length() == 0) text("조회 가능한 장비가 없습니다.", false);
            for (int i = 0; i < devices.length(); i++) {
                JSONObject item = devices.getJSONObject(i);
                String s = item.getString("site_id"), d = item.getString("device_id");
                dashboard.device(content, item,
                    () -> { site = s; device = d; navigate("details"); },
                    () -> { site = s; device = d; navigate("alarms"); });
            }
            return;
        }
        text(site + " / " + device, true);
        LinearLayout tabs = new LinearLayout(this);
        button(tabs, "상태", () -> navigate("details"));
        button(tabs, "이력", () -> navigate("history"));
        button(tabs, "알람", () -> navigate("alarms")); content.addView(tabs);
        if (requestedPage.equals("details")) {
            dashboard.details(content, response);
        } else if (requestedPage.equals("history")) {
            JSONArray history = response.getJSONArray("history");
            if (history.length() == 0) text("저장된 이력이 없습니다.", false);
            for (int i = 0; i < history.length(); i++) {
                JSONObject h = history.getJSONObject(i);
                text(h.optString("captured_at") + " · " + h.optString("kind"), true);
                text("알람: " + h.optString("alarms", "[]") + "\n고장: " + h.optString("faults", "[]"), false);
                JSONObject modules = h.optJSONObject("module_data");
                if (modules != null) {
                    text("실제 측정: " + value(h, "last_poll_at") + (h.optBoolean("connected") && h.optBoolean("last_poll_ok") ? "" : " · 통신 불량 / 이전값"), false);
                    for (Iterator<String> it = modules.keys(); it.hasNext();) {
                        String key = it.next(); JSONObject m = modules.optJSONObject(key); if (m == null) continue;
                        text("측정 행 " + key + " · SOC " + value(m, "soc") + "% · " + value(m, "volt") + " V · " + value(m, "current") + " A", false);
                        button(content, "측정 행 " + key + " 셀 기록", () -> showCells(key, m));
                    }
                }
                if (!h.isNull("raw_trap")) text("Trap: " + h.opt("raw_trap"), false);
            }
        } else {
            JSONArray active = response.getJSONArray("active"), events = response.getJSONArray("events");
            text("활성 알람 " + active.length() + "건", true);
            for (int i = 0; i < active.length(); i++) text(active.getJSONObject(i).optString("message"), false);
            text("발생 / 복구 이력", true);
            for (int i = 0; i < events.length(); i++) {
                JSONObject e = events.getJSONObject(i);
                text((e.optString("transition").equals("raised") ? "발생" : "복구") + " · " +
                    new java.util.Date((long)(e.optDouble("created_at") * 1000)) + "\n" + e.optString("message"), false);
                if (e.isNull("acknowledged_at")) {
                    String id = e.getString("event_id"); button(content, "확인 기록", () -> acknowledge(id));
                } else text("사용자 확인 완료", false);
            }
        }
    }

    private String value(JSONObject object, String key) { return object.isNull(key) ? "-" : object.optString(key, "-"); }
    private String cell(JSONArray array, int i) { return array == null || i >= array.length() || array.isNull(i) ? "-" : array.optString(i, "-"); }

    private void showCells(String module, JSONObject values) {
        JSONArray volts = values.optJSONArray("cells"), temps = values.optJSONArray("temps");
        int count = Math.max(volts == null ? 0 : volts.length(), temps == null ? 0 : temps.length());
        StringBuilder message = new StringBuilder();
        for (int i = 0; i < count; i++) message.append("셀 ").append(i + 1).append("   ").append(cell(volts, i)).append(" V / ").append(cell(temps, i)).append(" °C\n");
        new AlertDialog.Builder(this).setTitle("측정 행 " + module + " 셀 기록").setMessage(count == 0 ? "셀 정보 없음" : message.toString()).setPositiveButton("닫기", null).show();
    }

    private void acknowledge(String id) {
        if (busy) return; busy = true;
        network.execute(() -> {
            try {
                new ApiClient(settings.url(), settings.token()).request("POST", "/api/v1/acknowledgements", new JSONObject().put("event_id", id));
                runOnUiThread(() -> { busy = false; refresh(); });
            } catch (Exception e) { runOnUiThread(() -> { busy = false; status.setText("확인 기록 실패: " + e.getMessage()); }); }
        });
    }

    private void showSettings() {
        if (settingsDialog != null && settingsDialog.isShowing()) return;
        settingsDialog = new ConnectionSettingsDialog(this, settings, this::changeSettings);
        settingsDialog.setOnDismissListener(d -> {
            settingsDialog = null;
            if (resumed && !busy) refresh();
        });
        settingsDialog.show();
    }

    private void changeSettings(String url, String token, int interval, boolean logout, ConnectionSettingsDialog dialog) {
        if (busy) { dialog.showError("현재 조회를 마무리하고 있습니다. 잠시 후 다시 저장하세요."); return; }
        busy = true; generation++; dialog.saving(true);
        network.execute(() -> {
            try {
                synchronized (PushBridge.LOCK) {
                if (logout || !url.equals(settings.url()) || !token.equals(settings.token())) PushBridge.unregister(this);
                if (logout) settings.clear(); else settings.save(url, token, interval);
                }
                runOnUiThread(() -> {
                    busy = false; page = "devices"; content.removeAllViews(); dialog.dismiss();
                    if (!logout) PushBridge.initialize(this);
                    refresh();
                });
            } catch (Exception e) {
                runOnUiThread(() -> { busy = false; dialog.saving(false); dialog.showError("설정을 적용하지 못했습니다. 서버 연결과 이전 알림 등록 해제를 확인하세요.\n" + e.getMessage()); });
            }
        });
    }
}
