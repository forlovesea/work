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
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private boolean resumed, busy;
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
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(20, 24, 20, 12);
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            root.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(android.view.WindowInsets.Type.systemBars());
                view.setPadding(20 + bars.left, 24 + bars.top, 20 + bars.right, 12 + bars.bottom);
                return insets;
            });
        }
        root.setBackgroundColor(Color.rgb(245, 247, 250));
        TextView title = new TextView(this);
        title.setText("BatteryWatch"); title.setTextSize(26); title.setTextColor(Color.rgb(20, 70, 65));
        root.addView(title);
        LinearLayout actions = new LinearLayout(this);
        button(actions, "장비", () -> navigate("devices"));
        button(actions, "설정", this::showSettings);
        button(actions, "새로고침", this::refresh);
        root.addView(actions);
        status = new TextView(this); status.setPadding(0, 12, 0, 12); root.addView(status);
        ScrollView scroll = new ScrollView(this);
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
    @Override protected void onDestroy() { generation++; handler.removeCallbacksAndMessages(null); network.shutdownNow(); super.onDestroy(); }

    private void button(LinearLayout parent, String label, Runnable action) {
        Button b = new Button(this); b.setText(label); b.setOnClickListener(v -> action.run());
        parent.addView(b);
    }

    private void text(String value, boolean heading) {
        TextView view = new TextView(this); view.setText(value); view.setTextSize(heading ? 20 : 16);
        view.setTextColor(Color.rgb(35, 45, 55)); view.setPadding(6, 12, 6, 12); content.addView(view);
    }

    private void navigate(String next) { page = next; generation++; content.removeAllViews(); refresh(); }

    private void refresh() {
        if (busy || isFinishing()) return;
        if (settings.url().isEmpty()) { status.setText("설정에서 서버 주소와 조회 토큰을 입력하세요."); return; }
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
                    if (requestGeneration != generation || isFinishing()) return;
                    try { render(requestedPage, response); }
                    catch (Exception e) { status.setText("서버 데이터 형식을 확인하세요."); }
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    busy = false;
                    if (requestGeneration != generation || isFinishing()) return;
                    status.setText("조회 실패 — 표시된 값은 이전 데이터입니다.\n" + e.getMessage());
                    status.setTextColor(Color.rgb(160, 45, 35));
                });
            }
        });
    }

    private void render(String requestedPage, JSONObject response) throws JSONException {
        content.removeAllViews(); status.setTextColor(Color.rgb(65, 75, 85));
        status.setText("서버 응답: " + response.optString("server_time", ""));
        if (requestedPage.equals("devices")) {
            JSONArray devices = response.getJSONArray("devices");
            if (devices.length() == 0) text("조회 가능한 장비가 없습니다.", false);
            for (int i = 0; i < devices.length(); i++) {
                JSONObject item = devices.getJSONObject(i);
                String s = item.getString("site_id"), d = item.getString("device_id");
                text(s + " / " + d, true);
                text(!item.optBoolean("available") ? "수신 데이터 없음" :
                    (item.optBoolean("fresh") ? "정상 수신" : "통신 실패 / 오래된 데이터") +
                    " · 모듈 " + item.optInt("module_count") + " · 장비 알람 " + value(item, "alarm_count"), false);
                button(content, "상세 보기", () -> { site = s; device = d; navigate("details"); });
                button(content, "알람 보기", () -> { site = s; device = d; navigate("alarms"); });
            }
            return;
        }
        text(site + " / " + device, true);
        LinearLayout tabs = new LinearLayout(this);
        button(tabs, "상태", () -> navigate("details"));
        button(tabs, "이력", () -> navigate("history"));
        button(tabs, "알람", () -> navigate("alarms")); content.addView(tabs);
        if (requestedPage.equals("details")) {
            JSONObject data = response.getJSONObject("payload").getJSONObject("data");
            text(response.optBoolean("fresh") ? "정상 수신" : "통신 실패 / 오래된 데이터 — 현재 정상 값으로 사용하지 마세요.", true);
            text("측정: " + data.optString("last_poll_at", "-") + "\n서버 수신: " + response.optString("received_at", "-"), false);
            JSONObject modules = data.optJSONObject("module_data");
            if (modules == null || modules.length() == 0) text("모듈 정보 없음", false);
            else for (Iterator<String> it = modules.keys(); it.hasNext();) {
                String key = it.next(); JSONObject m = modules.optJSONObject(key); if (m == null) continue;
                text("모듈 " + key, true);
                text("SOC " + value(m, "soc") + "% · SOH " + value(m, "soh") + "%\n전압 " + value(m, "volt") + " V · 전류 " + value(m, "current") + " A", false);
                JSONArray volts = m.optJSONArray("cells"), temps = m.optJSONArray("temps");
                int count = Math.max(volts == null ? 0 : volts.length(), temps == null ? 0 : temps.length());
                for (int i = 0; i < count; i++) text("셀 " + (i + 1) + "   " + cell(volts, i) + " V   /   " + cell(temps, i) + " °C", false);
            }
            text("장비 알람", true); text(data.opt("active_alarms") == null ? "정보 없음" : data.opt("active_alarms").toString(), false);
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
                        text("모듈 " + key + " · SOC " + value(m, "soc") + "% · " + value(m, "volt") + " V · " + value(m, "current") + " A", false);
                        button(content, "모듈 " + key + " 셀 기록", () -> showCells(key, m));
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
        new AlertDialog.Builder(this).setTitle("모듈 " + module + " 셀 기록").setMessage(count == 0 ? "셀 정보 없음" : message.toString()).setPositiveButton("닫기", null).show();
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
        LinearLayout form = new LinearLayout(this); form.setOrientation(LinearLayout.VERTICAL); form.setPadding(30, 10, 30, 10);
        EditText url = new EditText(this); url.setHint("https://서버주소:8443"); url.setSingleLine(); url.setText(settings.url()); form.addView(url);
        EditText token = new EditText(this); token.setHint("조회용 토큰"); token.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD); form.addView(token);
        try { token.setText(settings.token()); } catch (Exception e) { status.setText("저장된 토큰을 다시 입력하세요."); }
        EditText interval = new EditText(this); interval.setHint("조회 주기 (5~300초)"); interval.setInputType(InputType.TYPE_CLASS_NUMBER); interval.setText(String.valueOf(settings.interval())); form.addView(interval);
        TextView push = new TextView(this); push.setText(PushBridge.description(this)); form.addView(push);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("서버 연결 설정").setView(form)
            .setPositiveButton("저장", null).setNegativeButton("취소", null).setNeutralButton("로그아웃", null).create();
        dialog.setOnShowListener(v -> {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(b -> {
                try {
                    String endpoint = Endpoint.validate(url.getText().toString(), BuildConfig.DEBUG);
                    String secret = token.getText().toString().trim(); int seconds = Integer.parseInt(interval.getText().toString());
                    if (secret.isEmpty() || seconds < 5 || seconds > 300) throw new IllegalArgumentException("토큰과 조회 주기를 확인하세요.");
                    changeSettings(endpoint, secret, seconds, false, dialog);
                } catch (Exception e) { token.setError(e.getMessage()); }
            });
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(b -> changeSettings("", "", 5, true, dialog));
        });
        dialog.show();
    }

    private void changeSettings(String url, String token, int interval, boolean logout, AlertDialog dialog) {
        if (busy) { status.setText("현재 조회가 끝난 뒤 다시 저장하세요."); return; }
        busy = true; generation++;
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
                runOnUiThread(() -> { busy = false; status.setText("설정 변경 실패 (이전 서버 알림 등록 해제 포함): " + e.getMessage()); });
            }
        });
    }
}
