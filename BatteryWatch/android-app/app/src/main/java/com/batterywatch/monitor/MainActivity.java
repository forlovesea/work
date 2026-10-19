package com.batterywatch.monitor;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.graphics.Color;
import android.text.InputType;
import android.text.InputFilter;
import android.view.View;
import android.widget.*;
import org.json.*;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Iterator;
import java.util.HashSet;
import java.util.Set;
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
    private String pendingControlCommand;
    private long controlCommandDeadline;
    private String site = "", device = "", page = "devices";
    private final Set<String> selectedEvents = new HashSet<>();
    private AlertDialog historyDeleteDialog;
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
        LinearLayout serverPanel = navigationPanel(root, false);
        LinearLayout actions = new LinearLayout(this);
        navigationButton(actions, "장비", false, false, () -> navigate("devices"));
        navigationButton(actions, "설정", false, false, this::showSettings);
        navigationButton(actions, "새로고침", false, false, this::refresh);
        serverPanel.addView(actions);
        status = new TextView(this); status.setTextSize(12); status.setTextColor(BatteryDashboard.MUTED); status.setPadding(0, dashboard.dp(10), 0, 0); serverPanel.addView(status);
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
    @Override protected void onDestroy() { resumed = false; generation++; if (historyDeleteDialog != null) historyDeleteDialog.dismiss(); if (settingsDialog != null) settingsDialog.dismiss(); handler.removeCallbacksAndMessages(null); network.shutdownNow(); super.onDestroy(); }

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

    private LinearLayout navigationPanel(LinearLayout parent, boolean devicePanel) {
        LinearLayout panel = dashboard.card(parent);
        android.graphics.drawable.GradientDrawable background = dashboard.background(
            devicePanel ? Color.rgb(19, 43, 45) : Color.rgb(24, 37, 55), 18);
        background.setStroke(dashboard.dp(1), devicePanel ? Color.rgb(43, 80, 77) : Color.rgb(49, 68, 92));
        panel.setBackground(background);
        return panel;
    }

    private Button navigationButton(LinearLayout parent, String title, boolean devicePanel, boolean selected, Runnable action) {
        Button button = new Button(this);
        button.setText(title); button.setTextSize(13); button.setAllCaps(false);
        button.setMinWidth(0); button.setMinimumWidth(0);
        button.setPadding(dashboard.dp(4), 0, dashboard.dp(4), 0);
        button.setTextColor(selected ? Color.rgb(12, 39, 35) :
            devicePanel ? Color.rgb(175, 222, 210) : Color.rgb(195, 216, 244));
        int fill = selected ? Color.rgb(116, 210, 185) :
            devicePanel ? Color.rgb(30, 65, 62) : Color.rgb(39, 58, 82);
        button.setBackgroundTintList(null);
        button.setBackground(new android.graphics.drawable.RippleDrawable(
            android.content.res.ColorStateList.valueOf(Color.argb(55, 220, 245, 255)),
            dashboard.background(fill, 12), null));
        button.setSelected(selected);
        button.setElevation(0);
        button.setOnClickListener(v -> action.run());
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dashboard.dp(48), 1);
        if (parent.getChildCount() > 0) params.setMarginStart(dashboard.dp(8));
        parent.addView(button, params);
        return button;
    }

    private void text(String value, boolean heading) {
        TextView view = new TextView(this); view.setText(value); view.setTextSize(heading ? 20 : 16);
        view.setTextColor(heading ? BatteryDashboard.INK : BatteryDashboard.MUTED); view.setPadding(6, 12, 6, 12); content.addView(view);
    }

    private void navigate(String next) { selectedEvents.clear(); page = next; generation++; content.removeAllViews(); scroll.scrollTo(0, 0); refresh(); }

    private void refresh() {
        if (closing || network.isShutdown() || busy || isFinishing() || historyDeleteDialog != null || (settingsDialog != null && settingsDialog.isShowing())) return;
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
                // Fetch current alarms even while viewing status or historical measurements.
                JSONObject alarms = requestedPage.equals("devices") ? null :
                    requestedPage.equals("alarms") ? response :
                    api.get("/api/v1/alarms" + ApiClient.query(selectedSite, selectedDevice));
                runOnUiThread(() -> {
                    busy = false;
                    if (closing || isFinishing() || isDestroyed()) return;
                    if (requestGeneration != generation) { refresh(); return; }
                    try { int y = scroll.getScrollY(); render(requestedPage, response, alarms); scroll.post(() -> scroll.scrollTo(0, y)); }
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

    private void render(String requestedPage, JSONObject response, JSONObject alarms) throws JSONException {
        content.removeAllViews(); content.setAlpha(1f); status.setTextColor(BatteryDashboard.MUTED);
        status.setText("서버 응답: " + DisplayTime.format(response.optString("server_time", "")));
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
        LinearLayout devicePanel = navigationPanel(content, true);
        TextView identity = dashboard.label(site + " / " + device, 20, BatteryDashboard.INK);
        identity.setPadding(0, 0, 0, dashboard.dp(12));
        devicePanel.addView(identity);
        LinearLayout tabs = new LinearLayout(this);
        navigationButton(tabs, "상태", true, requestedPage.equals("details"), () -> navigate("details"));
        navigationButton(tabs, "이력", true, requestedPage.equals("history"), () -> navigate("history"));
        Button alarmButton = navigationButton(tabs, "알람", true, requestedPage.equals("alarms"), () -> navigate("alarms"));
        dashboard.styleAlarmButton(alarmButton, alarms);
        devicePanel.addView(tabs);
        if (requestedPage.equals("details")) {
            boolean fresh = response.optBoolean("fresh");
            TextView reception = dashboard.label(fresh ? "● 정상 수신" : "● 오래된 데이터 · 현재 상태 확인 필요",
                14, fresh ? BatteryDashboard.GREEN : BatteryDashboard.AMBER);
            reception.setPadding(0, dashboard.dp(12), 0, 0);
            devicePanel.addView(reception);
            dashboard.details(content, response, () -> showChargeLimitDialog(response));
        } else if (requestedPage.equals("history")) {
            JSONArray history = response.getJSONArray("history");
            if (history.length() == 0) text("저장된 이력이 없습니다.", false);
            for (int i = 0; i < history.length(); i++) {
                JSONObject h = history.getJSONObject(i);
                text(DisplayTime.format(h.optString("captured_at")) + " · " + h.optString("kind"), true);
                JSONObject alarmData=new JSONObject()
                    .put("active_alarms",h.opt("alarms"))
                    .put("system_name",h.optString("system_name"))
                    .put("row_to_module",h.opt("row_to_module"))
                    .put("module_map",h.opt("module_map"));
                dashboard.deviceAlarms(content,alarmData);
                text("고장: " + h.optString("faults", "[]"), false);
                JSONObject modules = h.optJSONObject("module_data");
                if (modules != null) {
                    text("실제 측정: " + DisplayTime.format(h.optString("last_poll_at")) + (h.optBoolean("connected") && h.optBoolean("last_poll_ok") ? "" : " · 통신 불량 / 이전값"), false);
                    for (Iterator<String> it = modules.keys(); it.hasNext();) {
                        String key = it.next(); JSONObject m = modules.optJSONObject(key); if (m == null) continue;
                        text("측정 행 " + key + " · SOC " + value(m, "soc") + "% · " + value(m, "volt") + " V · " + value(m, "current") + " A", false);
                        button(content, "측정 행 " + key + " 셀 기록", () -> showCells(key, m));
                    }
                }
                if (!h.isNull("raw_trap")) text("Trap: " + h.opt("raw_trap"), false);
            }
        } else {
            JSONArray events = response.getJSONArray("events");
            dashboard.currentAlarmCards(content,response);
            text("발생 / 복구 이력", true);
            Set<String> visibleIds = new HashSet<>();
            for (int i = 0; i < events.length(); i++) visibleIds.add(events.getJSONObject(i).getString("event_id"));
            selectedEvents.retainAll(visibleIds);
            LinearLayout historyActions = new LinearLayout(this);
            content.addView(historyActions);
            Button deleteSelected = navigationButton(historyActions, "선택 삭제 (" + selectedEvents.size() + ")", true, false,
                () -> confirmHistoryDeletion(false));
            deleteSelected.setEnabled(!selectedEvents.isEmpty());
            Button deleteAll = navigationButton(historyActions, "전체 삭제", true, false,
                () -> confirmHistoryDeletion(true));
            deleteAll.setEnabled(events.length() > 0);
            if (events.length() == 0) text("저장된 발생 / 복구 이력이 없습니다.", false);
            for (int i = 0; i < events.length(); i++) {
                JSONObject e = events.getJSONObject(i);
                String eventId = e.getString("event_id");
                boolean raised = e.optString("transition").equals("raised");
                int ink = raised ? Color.rgb(105, 56, 44) : Color.rgb(35, 86, 72);
                int fill = raised ? (i % 2 == 0 ? Color.rgb(255, 235, 226) : Color.rgb(255, 244, 233))
                    : (i % 2 == 0 ? Color.rgb(225, 244, 236) : Color.rgb(236, 248, 242));
                LinearLayout eventCard = new LinearLayout(this);
                eventCard.setOrientation(LinearLayout.VERTICAL);
                eventCard.setPadding(dashboard.dp(12), dashboard.dp(10), dashboard.dp(12), dashboard.dp(12));
                android.graphics.drawable.GradientDrawable cardBackground = dashboard.background(fill, 14);
                cardBackground.setStroke(dashboard.dp(1), raised ? Color.rgb(232, 195, 180) : Color.rgb(174, 213, 196));
                eventCard.setBackground(cardBackground);
                LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(-1, -2);
                cardParams.topMargin = dashboard.dp(12);
                content.addView(eventCard, cardParams);
                CheckBox selected = new CheckBox(this);
                selected.setText((raised ? "발생" : "복구") + " · " +
                    DisplayTime.epoch(e.optDouble("created_at")) + "\n" + e.optString("message"));
                selected.setTextColor(ink);
                selected.setButtonTintList(android.content.res.ColorStateList.valueOf(ink));
                selected.setTextSize(16);
                selected.setLineSpacing(dashboard.dp(5), 1.12f);
                selected.setPadding(dashboard.dp(4), dashboard.dp(6), dashboard.dp(4), dashboard.dp(10));
                selected.setMinHeight(dashboard.dp(48));
                selected.setChecked(selectedEvents.contains(eventId));
                selected.setOnCheckedChangeListener((view, checked) -> {
                    if (checked) selectedEvents.add(eventId); else selectedEvents.remove(eventId);
                    deleteSelected.setText("선택 삭제 (" + selectedEvents.size() + ")");
                    deleteSelected.setEnabled(!selectedEvents.isEmpty());
                });
                eventCard.addView(selected);
                View divider = new View(this);
                divider.setBackgroundColor(raised ? Color.rgb(232, 205, 191) : Color.rgb(190, 220, 205));
                eventCard.addView(divider, new LinearLayout.LayoutParams(-1, dashboard.dp(1)));
                if (e.isNull("acknowledged_at")) {
                    Button acknowledgeButton = new Button(this);
                    acknowledgeButton.setText("확인 기록");
                    acknowledgeButton.setAllCaps(false);
                    acknowledgeButton.setTextColor(ink);
                    acknowledgeButton.setBackgroundTintList(android.content.res.ColorStateList.valueOf(
                        raised ? Color.rgb(246, 215, 200) : Color.rgb(201, 230, 216)));
                    acknowledgeButton.setOnClickListener(v -> acknowledge(eventId));
                    LinearLayout.LayoutParams actionParams = new LinearLayout.LayoutParams(-1, dashboard.dp(48));
                    actionParams.topMargin = dashboard.dp(8);
                    eventCard.addView(acknowledgeButton, actionParams);
                } else {
                    TextView acknowledged = dashboard.label("✓ 사용자 확인 완료", 14, ink);
                    acknowledged.setPadding(dashboard.dp(8), dashboard.dp(12), dashboard.dp(8), dashboard.dp(2));
                    eventCard.addView(acknowledged);
                }
            }
        }
    }

    private void confirmHistoryDeletion(boolean all) {
        if (historyDeleteDialog != null || (!all && selectedEvents.isEmpty())) return;
        final String targetSite = site, targetDevice = device;
        final Set<String> ids = new HashSet<>(selectedEvents);
        final int targetGeneration = generation;
        historyDeleteDialog = new AlertDialog.Builder(this)
            .setTitle(all ? "전체 이력 삭제" : "선택 이력 삭제")
            .setMessage(targetSite + " / " + targetDevice + "\n" +
                (all ? "화면에 표시되지 않은 이전 이력까지 모두 삭제합니다." : "선택한 " + ids.size() + "건을 삭제합니다.") +
                "\n현재 계정의 발생 / 복구 이력에서 삭제되며 현재 알람 상태는 유지됩니다.")
            .setNegativeButton("취소", null)
            .setPositiveButton("삭제", (dialog, which) -> {
                if (closing || network.isShutdown() || targetGeneration != generation) return;
                if (busy) {
                    Toast.makeText(this, "서버 조회 중입니다. 잠시 후 다시 삭제하세요.", Toast.LENGTH_SHORT).show();
                    return;
                }
                generation++;
                busy = true;
                status.setText("이력 삭제 중…");
                network.execute(() -> {
                    try {
                        final String url = settings.url(), token = settings.token();
                        JSONObject body = new JSONObject().put("site_id", targetSite).put("device_id", targetDevice);
                        if (all) body.put("all", true); else body.put("event_ids", new JSONArray(ids));
                        new ApiClient(url, token).request("POST", "/api/v1/alarms/delete-history", body);
                        runOnUiThread(() -> {
                            busy = false;
                            if (closing || isFinishing() || isDestroyed()) return;
                            selectedEvents.removeAll(ids);
                            Toast.makeText(this, "이력이 삭제되었습니다.", Toast.LENGTH_SHORT).show();
                            refresh();
                        });
                    } catch (Exception e) {
                        runOnUiThread(() -> {
                            busy = false;
                            if (closing || isFinishing() || isDestroyed()) return;
                            status.setText("이력 삭제 실패: " + e.getMessage());
                            status.setTextColor(BatteryDashboard.AMBER);
                        });
                    }
                });
            }).create();
        historyDeleteDialog.setOnDismissListener(dialog -> historyDeleteDialog = null);
        historyDeleteDialog.show();
    }

    private void showChargeLimitDialog(JSONObject snapshot) {
        if (busy || pendingControlCommand != null) {
            Toast.makeText(this,"이전 설정 요청이 처리 중입니다.",Toast.LENGTH_SHORT).show();
            return;
        }
        EditText input=new EditText(this);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_DECIMAL);
        input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(5)});
        JSONObject data=snapshot.optJSONObject("payload");
        JSONObject telemetry=data==null?null:data.optJSONObject("data");
        JSONObject status=telemetry==null?null:telemetry.optJSONObject("operating_status");
        Object current=status==null?null:status.opt("charge_current_limit_c");
        if(current!=null&&current!=JSONObject.NULL) input.setText(String.format(java.util.Locale.ROOT,"%.2f",
            current instanceof Number?((Number)current).doubleValue():Double.parseDouble(current.toString())));
        input.setSelection(input.length());
        new AlertDialog.Builder(this)
            .setTitle("충전전류제한 변경")
            .setMessage(site+" / "+device+" 장비에 원격 설정을 요청합니다.\n범위: 0.05~1.00 C\n온라인 모니터링 클라이언트가 장비에 적용하고 GET으로 확인합니다.")
            .setView(input)
            .setNegativeButton("취소",null)
            .setPositiveButton("장비에 설정 요청",(dialog,which)->{
                try {
                    BigDecimal value=new BigDecimal(input.getText().toString().trim())
                        .setScale(2,RoundingMode.UNNECESSARY);
                    int centi=value.movePointRight(2).intValueExact();
                    if(centi<5||centi>100) throw new NumberFormatException();
                    requestChargeLimit(centi);
                } catch (ArithmeticException|NumberFormatException e) {
                    new AlertDialog.Builder(this).setTitle("입력 오류")
                        .setMessage("0.05~1.00 사이 값을 소수점 둘째 자리까지 입력하세요.")
                        .setPositiveButton("확인",null).show();
                }
            }).show();
    }

    private void requestChargeLimit(int valueCenti) {
        if (busy || pendingControlCommand != null) return;
        busy=true;
        controlCommandDeadline=android.os.SystemClock.elapsedRealtime()+75000;
        status.setText("원격 설정 요청을 서버에 전송 중…");
        final String targetSite=site,targetDevice=device;
        network.execute(()->{
            try {
                JSONObject body=new JSONObject().put("site_id",targetSite).put("device_id",targetDevice)
                    .put("action","charge_current_limit").put("value_centi",valueCenti);
                JSONObject response=new ApiClient(settings.url(),settings.token())
                    .request("POST","/api/v1/commands",body);
                String commandId=response.getString("command_id");
                runOnUiThread(()->{
                    busy=false; pendingControlCommand=commandId;
                    status.setText("요청 전송됨 · 모니터링 클라이언트의 장비 적용 및 확인 대기 중…");
                    pollControlCommand(commandId);
                });
            } catch(Exception e) {
                runOnUiThread(()->{
                    busy=false;
                    status.setText("원격 설정 요청 실패: "+e.getMessage());
                    status.setTextColor(BatteryDashboard.AMBER);
                });
            }
        });
    }

    private void pollControlCommand(String commandId) {
        handler.postDelayed(()->{
            if(closing||!commandId.equals(pendingControlCommand)) return;
            if(android.os.SystemClock.elapsedRealtime()>=controlCommandDeadline) {
                pendingControlCommand=null;
                status.setText("원격 설정 결과 시간 초과 · 장비 상태를 새로 확인하세요.");
                status.setTextColor(BatteryDashboard.AMBER);
                return;
            }
            if(busy) { pollControlCommand(commandId); return; }
            busy=true;
            network.execute(()->{
                try {
                    JSONObject response=new ApiClient(settings.url(),settings.token())
                        .get("/api/v1/commands/"+commandId);
                    JSONObject command=response.getJSONObject("command");
                    String state=command.getString("status");
                    runOnUiThread(()->{
                        busy=false;
                        if(!commandId.equals(pendingControlCommand)) return;
                        if(state.equals("succeeded")) {
                            pendingControlCommand=null;
                            String applied=String.format(java.util.Locale.ROOT,"%.2f",
                                command.optInt("applied_value_centi")/100.0);
                            status.setText("충전전류제한 적용 및 장비 확인 완료: "+applied+" C");
                            status.setTextColor(BatteryDashboard.GREEN);
                            refresh();
                        } else if(state.equals("failed")||state.equals("timed_out")) {
                            pendingControlCommand=null;
                            status.setText("충전전류제한 설정 "+(state.equals("failed")?"실패: ":"시간 초과: ")
                                +command.optString("result_message","확인 필요"));
                            status.setTextColor(BatteryDashboard.AMBER);
                        } else {
                            status.setText("원격 설정 처리 중…");
                            pollControlCommand(commandId);
                        }
                    });
                } catch(Exception e) {
                    runOnUiThread(()->{
                        busy=false;
                        if(commandId.equals(pendingControlCommand)) {
                            pendingControlCommand=null;
                            status.setText("원격 설정 결과 확인 실패: "+e.getMessage());
                            status.setTextColor(BatteryDashboard.AMBER);
                        }
                    });
                }
            });
        },1500);
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
