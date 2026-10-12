package com.batterywatch.monitor;

import android.content.Context;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** Native dashboard using the supplied rack photograph; no synthetic telemetry. */
public final class BatteryDashboard {
    public static final int INK=Color.rgb(225,234,242), MUTED=Color.rgb(151,170,187),
        BG=Color.rgb(12,20,30), PANEL=Color.rgb(22,34,47), GREEN=Color.rgb(76,218,183),
        AMBER=Color.rgb(255,192,101);
    private final Context context;
    private String selectedId="";
    public BatteryDashboard(Context context) { this.context=context; }
    public int dp(float n) { return Math.round(n*context.getResources().getDisplayMetrics().density); }
    public GradientDrawable background(int color,int radius) {
        GradientDrawable d=new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(radius)); return d;
    }
    public TextView label(String text,int size,int color) {
        TextView t=new TextView(context); t.setText(text); t.setTextSize(size); t.setTextColor(color);
        t.setPadding(0,dp(4),0,dp(4)); return t;
    }
    public LinearLayout card(LinearLayout parent) {
        LinearLayout box=new LinearLayout(context); box.setOrientation(LinearLayout.VERTICAL); box.setPadding(dp(16),dp(14),dp(16),dp(14));
        box.setBackground(background(PANEL,18));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2); lp.setMargins(0,dp(8),0,dp(8));
        parent.addView(box,lp); return box;
    }
    public void empty(LinearLayout parent,Runnable settings) {
        LinearLayout c=card(parent);
        c.addView(label("BATTERY MONITOR",12,GREEN));
        c.addView(label("배터리 상태를\n한눈에 확인하세요",27,INK));
        c.addView(label("서버를 연결하면 등록된 모듈 1~10개의 상태와 셀 측정값을 확인할 수 있습니다.",15,MUTED));
        ImageView image=new ImageView(context); image.setImageResource(R.drawable.battery_rack);
        image.setScaleType(ImageView.ScaleType.FIT_CENTER); c.addView(image,new LinearLayout.LayoutParams(-1,dp(260)));
        c.addView(label("10개 장착 참고 사진 · 연결 전에는 측정값을 표시하지 않습니다.",12,MUTED));
        action(c,"서버 연결 설정",settings);
    }
    public void action(LinearLayout parent,String title,Runnable action) {
        Button b=new Button(context); b.setText(title); b.setTextColor(GREEN); b.setAllCaps(false);
        b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(34,54,66)));
        b.setOnClickListener(v->action.run()); parent.addView(b,new LinearLayout.LayoutParams(-1,dp(50)));
    }
    public void device(LinearLayout parent,JSONObject data,Runnable detail,Runnable alarms) {
        LinearLayout box=card(parent);
        box.addView(label(data.optString("site_id"),12,GREEN));
        box.addView(label(data.optString("device_id"),22,INK));
        boolean available=data.optBoolean("available"),fresh=data.optBoolean("fresh");
        box.addView(label(!available?"● 수신 데이터 없음":fresh?"● 정상 수신":"● 통신 실패 / 오래된 데이터",14,fresh&&available?GREEN:AMBER));
        if(available) box.addView(label("측정  "+DisplayTime.format(data.optString("last_poll_at"))
            +"\n수신  "+DisplayTime.format(data.optString("received_at"))
            +"\n"+DisplayTime.age(data.optDouble("measurement_age_seconds",Double.NaN)),12,MUTED));
        LinearLayout hero=new LinearLayout(context); hero.setGravity(Gravity.CENTER_VERTICAL);
        ImageView photo=new ImageView(context); photo.setImageResource(R.drawable.battery_rack);
        photo.setContentDescription("배터리 랙 참고 사진, 실제 구성은 상세 화면에서 확인");
        photo.setScaleType(ImageView.ScaleType.FIT_CENTER); hero.addView(photo,new LinearLayout.LayoutParams(dp(68),dp(188)));
        LinearLayout summary=new LinearLayout(context); summary.setOrientation(LinearLayout.VERTICAL); summary.setPadding(dp(18),0,0,0);
        summary.addView(label("등록 모듈",12,MUTED)); summary.addView(label(available?data.optInt("module_count")+" / 10":"— / 10",28,INK));
        summary.addView(label("장비 알람  "+(available?value(data,"alarm_count"):"—")+"건",14,MUTED));
        summary.addView(label("랙 사진은 10개 장착 예시",11,MUTED)); hero.addView(summary,new LinearLayout.LayoutParams(0,-2,1)); box.addView(hero);
        action(box,"모듈 상태 보기  →",detail); action(box,"알람 · 발생 / 복구 이력",alarms);
    }
    private static String value(JSONObject data,String key) { return data==null||data.isNull(key)?"—":data.optString(key,"—"); }
    private static String cell(JSONArray a,int i) { return a==null||a.isNull(i)?"—":a.optString(i,"—"); }
    private static String alarmSeverity(Object raw) {
        String value=raw==null||raw==JSONObject.NULL?"":raw.toString().trim();
        if("1".equals(value)||"critical".equalsIgnoreCase(value)) return "Critical";
        if("2".equals(value)||"major".equalsIgnoreCase(value)) return "Major";
        if("3".equals(value)||"minor".equalsIgnoreCase(value)) return "Minor";
        if("4".equals(value)||"warning".equalsIgnoreCase(value)||"warnning".equalsIgnoreCase(value)||"warring".equalsIgnoreCase(value)) return "Warning";
        return "Unknown";
    }
    private static int alarmSeverityColor(String severity) {
        switch(severity) {
            case "Critical": return Color.rgb(255,105,105);
            case "Major": return Color.rgb(255,166,77);
            case "Minor": return Color.rgb(255,211,92);
            case "Warning": return Color.rgb(91,181,255);
            default: return MUTED;
        }
    }
    private List<JSONObject> currentAlarms(JSONObject response) {
        List<JSONObject> alarms=new ArrayList<>();
        if(response==null) return alarms;
        JSONObject data=response.optJSONObject("device_alarms");
        Object raw=data==null?null:data.opt("active_alarms");
        if(raw instanceof JSONArray) {
            JSONArray array=(JSONArray)raw;
            for(int i=0;i<array.length();i++) if(array.optJSONObject(i)!=null) alarms.add(array.optJSONObject(i));
        } else if(raw instanceof JSONObject) {
            JSONObject object=(JSONObject)raw;
            if(object.has("text")||object.has("level")||object.has("time")) alarms.add(object);
            else for(Iterator<String> keys=object.keys();keys.hasNext();) {
                JSONObject alarm=object.optJSONObject(keys.next());
                if(alarm!=null) alarms.add(alarm);
            }
        }
        // The server also reports a single aggregate device condition: do not count it twice.
        JSONArray active=response.optJSONArray("active");
        boolean hasDeviceAlarms=!alarms.isEmpty();
        if(active!=null) for(int i=0;i<active.length();i++) {
            JSONObject alarm=active.optJSONObject(i);
            if(alarm!=null&&(!"device_alarms".equals(alarm.optString("rule_key"))||!hasDeviceAlarms)) alarms.add(alarm);
        }
        return alarms;
    }
    public void styleAlarmButton(Button button, JSONObject response) {
        if(response==null) return;
        List<JSONObject> alarms=currentAlarms(response);
        int count=alarms.size();
        button.setText(count==0?"알람":"알람("+count+")");
        if(count==0) return;
        int highest=5;
        for(JSONObject alarm:alarms) {
            String severity=alarmSeverity(alarm.has("level")?alarm.opt("level"):alarm.opt("severity"));
            int rank="Critical".equals(severity)?1:"Major".equals(severity)?2:
                "Minor".equals(severity)?3:"Warning".equals(severity)?4:5;
            highest=Math.min(highest,rank);
        }
        int fill=highest==1?Color.rgb(220,38,38):highest==2?Color.rgb(255,153,64):
            highest==3?Color.rgb(255,225,153):highest==4?Color.rgb(174,216,245):Color.rgb(213,198,238);
        button.setTextColor(highest==1?Color.WHITE:Color.rgb(30,40,55));
        button.setBackground(new android.graphics.drawable.RippleDrawable(
            android.content.res.ColorStateList.valueOf(Color.argb(55,255,255,255)),background(fill,12),null));
        String severity=highest==1?"Critical":highest==2?"Major":highest==3?"Minor":highest==4?"Warning":"Unknown";
        button.setContentDescription("알람 "+count+"건, 최고 심각도 "+severity);
        android.view.animation.AlphaAnimation blink=new android.view.animation.AlphaAnimation(1f,0.45f);
        blink.setDuration(700);
        blink.setRepeatMode(android.view.animation.Animation.REVERSE);
        blink.setRepeatCount(android.view.animation.Animation.INFINITE);
        button.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener() {
            @Override public void onViewAttachedToWindow(View view) { view.startAnimation(blink); }
            @Override public void onViewDetachedFromWindow(View view) { view.clearAnimation(); }
        });
        if(button.isAttachedToWindow()) button.startAnimation(blink);
    }
    private static int moduleNumber(JSONObject data,JSONObject alarm) {
        Object rawRow=alarm.opt("row_index");
        if(rawRow==null||rawRow==JSONObject.NULL) return -1;
        String row=rawRow.toString();
        JSONObject rowMap=data.optJSONObject("row_to_module");
        int number=validModuleNumber(rowMap==null?null:rowMap.opt(row));
        if(number>0) return number;
        JSONObject modules=data.optJSONObject("module_map");
        if(modules!=null) for(Iterator<String> i=modules.keys();i.hasNext();) {
            String id=i.next(); JSONObject module=modules.optJSONObject(id);
            if(module!=null&&row.equals(module.optString("row_index")))
                return validModuleNumber(id);
        }
        return -1;
    }
    private static int validModuleNumber(Object raw) {
        if(raw==null||raw==JSONObject.NULL) return -1;
        try { int number=Integer.parseInt(raw.toString()); return number>=1&&number<=10?number:-1; }
        catch(NumberFormatException e) { return -1; }
    }
    public void deviceAlarms(LinearLayout parent,JSONObject data) {
        LinearLayout section=card(parent);
        section.addView(label("장비 알람",18,INK));
        if(data==null) {
            section.addView(label("장비 알람 정보를 가져오지 못했습니다.",14,MUTED));
            return;
        }
        Object raw=data.opt("active_alarms");
        List<JSONObject> alarms=new ArrayList<>();
        boolean valid=true;
        if(!data.has("active_alarms")||raw==null||raw==JSONObject.NULL) {
            section.addView(label("알람 정보가 없습니다.",14,MUTED));
            return;
        }
        if(raw instanceof JSONArray) {
            JSONArray array=(JSONArray)raw;
            for(int i=0;i<array.length();i++) {
                JSONObject alarm=array.optJSONObject(i);
                if(alarm==null) valid=false; else alarms.add(alarm);
            }
        } else if(raw instanceof JSONObject) {
            JSONObject object=(JSONObject)raw;
            if(object.has("text")||object.has("level")||object.has("time")) alarms.add(object);
            else for(Iterator<String> i=object.keys();i.hasNext();) {
                JSONObject alarm=object.optJSONObject(i.next());
                if(alarm==null) valid=false; else alarms.add(alarm);
            }
        } else if(raw!=null&&raw!=JSONObject.NULL) valid=false;
        if(!valid) {
            section.addView(label("알람 데이터 형식을 확인할 수 없습니다.",14,AMBER));
            return;
        }
        if(alarms.isEmpty()) {
            section.addView(label("현재 발생한 장비 알람이 없습니다.",14,MUTED));
            return;
        }
        renderAlarmCards(section,data,alarms,false);
    }
    public void currentAlarmCards(LinearLayout parent,JSONObject response) {
        List<JSONObject> alarms=currentAlarms(response);
        LinearLayout section=card(parent);
        section.addView(label("현재 알람 "+alarms.size()+"건",18,INK));
        if(alarms.isEmpty()) {
            section.addView(label("현재 발생한 알람이 없습니다.",14,MUTED));
            return;
        }
        JSONObject data=response.optJSONObject("device_alarms");
        renderAlarmCards(section,data==null?new JSONObject():data,alarms,true);
    }
    private void renderAlarmCards(LinearLayout section,JSONObject data,List<JSONObject> alarms,boolean numbered) {
        String system=data.optString("system_name","").trim();
        if(system.isEmpty()) system=data.optString("connection_system_name","").trim();
        int number=0;
        for(JSONObject alarm:alarms) {
            boolean serverAlarm=alarm.has("rule_key");
            String severity=alarmSeverity(alarm.has("level")?alarm.opt("level"):alarm.opt("severity"));
            int color=alarmSeverityColor(severity);
            GradientDrawable outline=background(PANEL,14);
            outline.setStroke(dp(1),color);
            LinearLayout item=new LinearLayout(context);
            item.setOrientation(LinearLayout.VERTICAL);
            item.setPadding(dp(12),dp(10),dp(12),dp(10));
            item.setBackground(outline);
            LinearLayout.LayoutParams itemParams=new LinearLayout.LayoutParams(-1,-2);
            itemParams.setMargins(0,dp(5),0,dp(5));
            section.addView(item,itemParams);
            if(numbered) item.addView(label("알람("+(++number)+") · "+(serverAlarm?"서버 감시":"장비 알람"),16,INK));
            LinearLayout metadata=new LinearLayout(context);
            metadata.setGravity(Gravity.CENTER_VERTICAL);
            int module=moduleNumber(data,alarm);
            String location=module>0
                ?"모듈 "+module
                :alarm.has("row_index")?"모듈 확인 필요":"시스템";
            if(!system.isEmpty()) location=system+" · "+location;
            String time=alarm.optString("time","").trim();
            if(serverAlarm) {
                location="서버 감시";
                time=alarm.isNull("last_observed")?"":DisplayTime.epoch(alarm.optDouble("last_observed"));
                if(!time.isEmpty()) time="최근 감지 "+time;
            }
            TextView detail=label((time.isEmpty()?"—":time)+"  |  "+location,12,MUTED);
            metadata.addView(detail,new LinearLayout.LayoutParams(0,-2,1));
            TextView badge=label("Unknown".equals(severity)?"미분류":severity,12,color);
            badge.setPadding(dp(8),dp(3),dp(8),dp(3));
            badge.setBackground(background(Color.rgb(36,48,63),10));
            metadata.addView(badge);
            item.addView(metadata);
            String message=alarm.optString("text","").trim();
            if(serverAlarm) {
                String rule=alarm.optString("rule_key");
                message="communication".equals(rule)?"측정 통신 이상":
                    "device_alarms".equals(rule)?"장비 알람 발생 · 상세 정보 없음":alarm.optString("message","");
            }
            item.addView(label(message.isEmpty()?"(알람 내용 없음)":message,15,INK));
            if(serverAlarm&&"communication".equals(alarm.optString("rule_key")))
                item.addView(label("장비의 정상 측정 데이터를 받지 못하고 있습니다. 연결 상태와 데이터 갱신 시각을 확인하세요.",12,MUTED));
        }
    }
    public static List<ModuleSlots.Slot> slots(JSONObject data) {
        Map<String,String> mapping=new HashMap<>(); Set<String> rows=new HashSet<>();
        JSONObject map=data.optJSONObject("module_map"), values=data.optJSONObject("module_data");
        if(map!=null) for(Iterator<String> i=map.keys();i.hasNext();) { String id=i.next(); JSONObject m=map.optJSONObject(id);
            mapping.put(id,m==null||m.isNull("row_index")?null:m.optString("row_index",null)); }
        if(values!=null) for(Iterator<String> i=values.keys();i.hasNext();) rows.add(i.next());
        return ModuleSlots.resolve(mapping,rows);
    }
    public void details(LinearLayout parent,JSONObject response,Runnable changeChargeLimit) throws JSONException {
        JSONObject data=response.getJSONObject("payload").getJSONObject("data");
        JSONObject values=data.optJSONObject("module_data"); List<ModuleSlots.Slot> slots=slots(data);
        boolean fresh=response.optBoolean("fresh");
        LinearLayout summary=card(parent);
        long count=slots.stream().filter(s->s.mapped).count();
        summary.addView(label("배터리 모듈  "+count+" / 10",24,INK));
        rackSummary(summary,data,slots,fresh,changeChargeLimit);
        summary.addView(label("측정  "+DisplayTime.format(data.optString("last_poll_at"))+"\n수신  "+DisplayTime.format(response.optString("received_at")),12,MUTED));
        summary.addView(label(DisplayTime.age(response.optDouble("measurement_age_seconds",Double.NaN)),12,fresh?MUTED:AMBER));
        if(!fresh) {
            String reason=!data.optBoolean("connected")?"모니터링 클라이언트와 배터리 장비의 연결을 확인하세요.":
                !data.optBoolean("last_poll_ok")?"최근 장비 측정 실패 · 이전 측정값입니다.":
                "PC/서버 시계와 모니터링 클라이언트의 측정·전송 대기를 확인하세요.";
            summary.addView(label(reason,13,AMBER));
            if(!data.isNull("last_poll_error") && !data.optString("last_poll_error").isEmpty())
                summary.addView(label("측정 오류: "+data.optString("last_poll_error"),12,AMBER));
        }
        if(slots.isEmpty()) {
            summary.addView(label("등록된 모듈 정보가 없습니다.",16,AMBER));
            deviceAlarms(parent,data);
            return;
        }
        if(count>10) summary.addView(label("지원 수량(10개)을 초과한 데이터입니다. 서버 구성을 확인하세요.",14,AMBER));
        if(slots.stream().anyMatch(s->!s.mapped)) summary.addView(label("모듈 번호를 확인할 수 없는 측정 행이 있습니다. 미매핑 행으로 별도 표시합니다.",13,AMBER));
        LinearLayout selection=new LinearLayout(context); selection.setOrientation(LinearLayout.VERTICAL);
        LinearLayout rackCard=card(parent); rackCard.addView(label("RACK OVERVIEW",12,GREEN));
        rackCard.addView(label("모듈을 선택해 상세값을 확인하세요",15,INK));
        rackCard.addView(label("번호 내림차순 표시 · 실제 장착 위치와 다를 수 있음",11,MUTED));
        List<ModuleSlots.Slot> installed=new ArrayList<>(); for(ModuleSlots.Slot s:slots) if(s.mapped&&installed.size()<10) installed.add(s);
        Collections.reverse(installed);
        if(!installed.isEmpty()) {
            RackView rack=new RackView(context,installed,values,fresh);
            rack.choose=slot->{selectedId=slot.mapped+":"+slot.id;
                showModule(selection,slot,values==null||slot.row==null?null:values.optJSONObject(slot.row),fresh);
                rack.invalidate();
                selection.post(()->selection.requestRectangleOnScreen(new Rect(0,0,selection.getWidth(),dp(170)),false));};
            rackCard.addView(rack,new LinearLayout.LayoutParams(-1,dp(60+installed.size()*48)));
        }
        parent.addView(selection);
        ModuleSlots.Slot initial=slots.get(0); for(ModuleSlots.Slot s:slots) if((s.mapped+":"+s.id).equals(selectedId)) initial=s;
        selectedId=initial.mapped+":"+initial.id;
        HorizontalScrollView picker=new HorizontalScrollView(context);
        LinearLayout selectors=new LinearLayout(context); selectors.setOrientation(LinearLayout.HORIZONTAL);
        picker.addView(selectors); rackCard.addView(picker);
        for(ModuleSlots.Slot slot:slots) {
            JSONObject m=values==null||slot.row==null?null:values.optJSONObject(slot.row);
            Button b=new Button(context); b.setAllCaps(false); b.setText(slot.label()+"    SOC "+value(m,"soc")+"%    ›");
            b.setGravity(Gravity.START|Gravity.CENTER_VERTICAL); b.setTextColor(INK);
            b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(30,48,62)));
            selectors.addView(b,new LinearLayout.LayoutParams(-2,dp(48)));
            b.setOnClickListener(v->{ selectedId=slot.mapped+":"+slot.id; showModule(selection,slot,m,fresh);
                for(int i=0;i<rackCard.getChildCount();i++) if(rackCard.getChildAt(i) instanceof RackView) rackCard.getChildAt(i).invalidate();
                selection.requestFocus();
                selection.post(()->selection.requestRectangleOnScreen(new Rect(0,0,selection.getWidth(),dp(170)),false)); });
        }
        showModule(selection,initial,values==null||initial.row==null?null:values.optJSONObject(initial.row),fresh);
        deviceAlarms(parent,data);
    }
    private static Object summaryValue(JSONObject data,String title) {
        JSONArray table=data.optJSONArray("summary_table");
        if(table==null) return null;
        for(int r=0;r+1<table.length();r+=2) {
            JSONArray labels=table.optJSONArray(r),values=table.optJSONArray(r+1);
            if(labels==null||values==null) continue;
            for(int c=0;c<labels.length();c++) if(title.equals(labels.optString(c))) return values.opt(c);
        }
        return null;
    }
    private void rackSummary(LinearLayout parent,JSONObject data,List<ModuleSlots.Slot> slots,boolean fresh,
                             Runnable changeChargeLimit) {
        int color=fresh?INK:MUTED;
        LinearLayout electric=new LinearLayout(context);
        metric(electric,"전체 전압",RackSummary.number(summaryValue(data,"Rack 전압[V]"),false),"V",color);
        metric(electric,"전체 전류",RackSummary.number(summaryValue(data,"Rack 전류[A]"),false),"A",color);
        parent.addView(electric);
        LinearLayout health=new LinearLayout(context);
        metric(health,"전체 SOC",RackSummary.number(summaryValue(data,"SOC 충전율[%]"),true),"%",color);
        metric(health,"전체 SOH",RackSummary.number(data.opt("group_soh"),true),"%",color);
        parent.addView(health);
        RackSummary.Temperatures temperatures=new RackSummary.Temperatures();
        JSONObject rows=data.optJSONObject("module_data");
        Set<String> seen=new HashSet<>();
        if(rows!=null) for(ModuleSlots.Slot slot:slots) {
            if(slot.row==null||!seen.add(slot.row)) continue;
            JSONObject module=rows.optJSONObject(slot.row);
            JSONArray temps=module==null?null:module.optJSONArray("temps");
            if(temps!=null) for(int i=0;i<temps.length();i++) temperatures.add(slot.label(),temps.optDouble(i,Double.NaN));
        }
        LinearLayout thermal=new LinearLayout(context);
        metric(thermal,"최고 셀 온도",temperatures.maximum(),"°C",color);
        metric(thermal,"최저 셀 온도",temperatures.minimum(),"°C",color);
        parent.addView(thermal);
        LinearLayout origins=new LinearLayout(context);
        column(origins,temperatures.maxModules(),MUTED); column(origins,temperatures.minModules(),MUTED);
        parent.addView(origins);
        parent.addView(label("온도: 수신된 셀 기준 · 미수신 값은 — 표시",11,MUTED));
        operatingStatus(parent,data,fresh,changeChargeLimit);
    }
    private void operatingStatus(LinearLayout parent,JSONObject data,boolean fresh,Runnable changeChargeLimit) {
        JSONObject status=data.optJSONObject("operating_status");
        LinearLayout section=card(parent);
        section.addView(label("방전 · 충전 보호 및 제한",16,INK));
        LinearLayout metrics=new LinearLayout(context);
        Object discharge=status==null?summaryValue(data,"방전 횟수"):status.opt("discharge_count");
        Object chargeLimit=status==null?null:status.opt("charge_current_limit_c");
        metric(metrics,"방전 횟수",RackSummary.number(discharge,false),"회",fresh?INK:MUTED);
        metric(metrics,"충전전류제한",RackSummary.number(chargeLimit,false,2),"C",fresh?INK:MUTED);
        section.addView(metrics);
        if(fresh) action(section,"충전전류제한 변경",changeChargeLimit);
        else section.addView(label("새 측정값을 수신한 뒤 충전전류제한을 변경할 수 있습니다.",12,AMBER));

        JSONObject cutoffs=status==null?null:status.optJSONObject("charge_cutoff");
        addProtection(section,"과전압 충전차단",cutoffs==null?summaryValue(data,"과전압 충전차단"):cutoffs.opt("overvoltage"));
        addProtection(section,"고온 충전차단",cutoffs==null?summaryValue(data,"고온 충전차단"):cutoffs.opt("high_temperature"));
        addProtection(section,"과전류 충전차단",cutoffs==null?summaryValue(data,"과전류 충전차단"):cutoffs.opt("overcurrent"));
        addProtection(section,"차단기 OFF",cutoffs==null?summaryValue(data,"차단기 OFF"):cutoffs.opt("breaker_off"));

        JSONObject socLimit=status==null?null:status.optJSONObject("soc_charge_limit");
        if(socLimit!=null&&!socLimit.isNull("supported")) {
            if(socLimit.optBoolean("supported")) {
                boolean enabled=socLimit.optBoolean("enabled");
                String value=RackSummary.number(socLimit.opt("value_percent"),true);
                String text=socLimit.isNull("enabled")?"응답 없음":
                    enabled?"사용 · "+("—".equals(value)?"값 미수신":value+"%"):"미사용";
                section.addView(label("SOC 충전제한: "+text,14,enabled?GREEN:MUTED));
            }
        } else if(socLimit!=null) {
            section.addView(label("SOC 충전제한: 확인 중",14,MUTED));
        }
    }
    private void addProtection(LinearLayout parent,String title,Object value) {
        String state=RackSummary.protection(value);
        int color="발생".equals(state)?AMBER:"정상".equals(state)?GREEN:MUTED;
        LinearLayout row=new LinearLayout(context);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(0,dp(2),0,dp(2));
        TextView name=label(title,14,INK);
        row.addView(name,new LinearLayout.LayoutParams(0,-2,1));
        TextView badge=label(state,13,color);
        badge.setGravity(Gravity.CENTER);
        badge.setMinWidth(dp(68));
        badge.setPadding(dp(10),dp(3),dp(10),dp(3));
        badge.setBackground(background(Color.rgb(34,54,66),12));
        row.addView(badge,new LinearLayout.LayoutParams(-2,-2));
        parent.addView(row,new LinearLayout.LayoutParams(-1,-2));
    }
    private void showModule(LinearLayout parent,ModuleSlots.Slot slot,JSONObject m,boolean fresh) {
        parent.removeAllViews(); LinearLayout box=card(parent);
        box.addView(label(slot.label(),23,INK));
        if(!fresh) box.addView(label("이전 수신값 · 현재 정상 값으로 사용하지 마세요",13,AMBER));
        if(m==null) { box.addView(label("이 모듈의 측정 데이터가 없습니다.",15,AMBER)); return; }
        Object communication=m.isNull("communication_status")?m.opt("status"):m.opt("communication_status");
        String communicationStatus=RackSummary.communicationStatus(communication);
        int communicationColor="Online".equals(communicationStatus)||"충전중".equals(communicationStatus)
            ||"방전중".equals(communicationStatus)||"Standby".equals(communicationStatus)?GREEN:
            "Offline".equals(communicationStatus)||"Disconnect".equals(communicationStatus)?AMBER:MUTED;
        box.addView(label("통신 상태: "+communicationStatus,14,communicationColor));
        LinearLayout metrics=new LinearLayout(context);
        metric(metrics,"SOC",value(m,"soc"),"%",fresh?GREEN:MUTED); metric(metrics,"SOH",value(m,"soh"),"%",INK);box.addView(metrics);
        double soc=m.optDouble("soc",Double.NaN);
        if(Double.isFinite(soc)&&soc>=0&&soc<=100) {
            ProgressBar gauge=new ProgressBar(context,null,android.R.attr.progressBarStyleHorizontal);
            gauge.setMax(1000);gauge.setProgress((int)Math.round(soc*10));
            gauge.setProgressTintList(android.content.res.ColorStateList.valueOf(fresh?GREEN:MUTED));
            gauge.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(45,62,77)));
            gauge.setContentDescription("충전 상태 "+value(m,"soc")+" 퍼센트");box.addView(gauge,new LinearLayout.LayoutParams(-1,dp(12)));
        }
        LinearLayout electric=new LinearLayout(context);metric(electric,"전압",value(m,"volt"),"V",INK);metric(electric,"전류",value(m,"current"),"A",INK);box.addView(electric);
        box.addView(label("셀 상세",18,INK));
        JSONArray volts=m.optJSONArray("cells"),temps=m.optJSONArray("temps");
        int count=Math.max(volts==null?0:volts.length(),temps==null?0:temps.length());
        if(count==0) box.addView(label("셀 정보 없음",14,MUTED));
        LinearLayout heading=new LinearLayout(context);column(heading,"셀",MUTED);column(heading,"전압 (V)",MUTED);column(heading,"온도 (°C)",MUTED);box.addView(heading);
        for(int i=0;i<count;i++) {LinearLayout row=new LinearLayout(context);row.setPadding(dp(8),dp(6),dp(8),dp(6));
            if(i%2==0) row.setBackground(background(Color.rgb(29,44,58),7));
            column(row,String.format(Locale.ROOT,"%02d",i+1),MUTED);column(row,cell(volts,i),INK);column(row,cell(temps,i),INK);box.addView(row);}
    }
    private void column(LinearLayout row,String s,int color){row.addView(label(s,14,color),new LinearLayout.LayoutParams(0,-2,1));}
    private void metric(LinearLayout row,String title,String value,String unit,int color) {
        LinearLayout c=new LinearLayout(context); c.setOrientation(LinearLayout.VERTICAL);c.setPadding(0,dp(8),0,dp(8));
        c.addView(label(title,12,MUTED));c.addView(label(value+" "+unit,25,color));row.addView(c,new LinearLayout.LayoutParams(0,-2,1));
    }
    private final class RackView extends View {
        private final Bitmap photo;
        private final List<ModuleSlots.Slot> modules;
        private final JSONObject values;
        private final boolean fresh;
        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
        private final Rect source=new Rect();
        private final RectF destination=new RectF();
        java.util.function.Consumer<ModuleSlots.Slot> choose;
        RackView(Context c,List<ModuleSlots.Slot> modules,JSONObject values,boolean fresh) {
            super(c);this.modules=modules;this.values=values;this.fresh=fresh;
            photo=BitmapFactory.decodeResource(getResources(),R.drawable.battery_rack);
            setContentDescription("등록된 배터리 모듈 "+modules.size()+"개. 아래 모듈 버튼에서 상세 정보를 확인하세요.");
        }
        @Override public boolean performClick() { super.performClick(); return true; }
        @Override public boolean onTouchEvent(android.view.MotionEvent e) {
            if(e.getAction()==android.view.MotionEvent.ACTION_DOWN) return true;
            if(e.getAction()==android.view.MotionEvent.ACTION_UP) {
                performClick(); int i=(int)((e.getY()-dp(44))/dp(48));
                if(e.getY()>=dp(44)&&i>=0&&i<modules.size()&&choose!=null) choose.accept(modules.get(i)); return true;
            }
            return super.onTouchEvent(e);
        }
        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);float w=getWidth(),left=dp(4),right=w*.46f,top=dp(12),step=dp(48);
            p.setColor(Color.rgb(7,12,18));canvas.drawRoundRect(left,top,right,top+dp(34)+modules.size()*step,dp(7),dp(7),p);
            if(photo!=null) { source.set(0,0,photo.getWidth(),50);destination.set(left,top,right,top+dp(32));canvas.drawBitmap(photo,source,destination,p); }
            for(int i=0;i<modules.size();i++) {
                float y=top+dp(32)+i*step;ModuleSlots.Slot slot=modules.get(i);
                if((slot.mapped+":"+slot.id).equals(selectedId)) {
                    p.setColor(Color.rgb(28,66,65));canvas.drawRoundRect(right+dp(5),y,w,y+step-dp(2),dp(7),dp(7),p);
                }
                if(photo!=null) { source.set(0,50,photo.getWidth(),90);destination.set(left,y,right,y+step-dp(2));canvas.drawBitmap(photo,source,destination,p); }
                JSONObject m=values==null||slot.row==null?null:values.optJSONObject(slot.row);
                p.setColor(fresh&&m!=null?GREEN:AMBER);canvas.drawCircle(right+dp(12),y+step/2,dp(3),p);
                p.setTextSize(dp(12));p.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
                canvas.drawText(slot.label(),right+dp(23),y+dp(19),p);
                p.setColor(MUTED);p.setTextSize(dp(11));canvas.drawText("SOC "+value(m,"soc")+"%",right+dp(23),y+dp(36),p);
            }
        }
    }
}
