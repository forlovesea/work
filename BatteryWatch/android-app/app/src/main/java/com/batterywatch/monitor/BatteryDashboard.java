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
    public static List<ModuleSlots.Slot> slots(JSONObject data) {
        Map<String,String> mapping=new HashMap<>(); Set<String> rows=new HashSet<>();
        JSONObject map=data.optJSONObject("module_map"), values=data.optJSONObject("module_data");
        if(map!=null) for(Iterator<String> i=map.keys();i.hasNext();) { String id=i.next(); JSONObject m=map.optJSONObject(id);
            mapping.put(id,m==null||m.isNull("row_index")?null:m.optString("row_index",null)); }
        if(values!=null) for(Iterator<String> i=values.keys();i.hasNext();) rows.add(i.next());
        return ModuleSlots.resolve(mapping,rows);
    }
    public void details(LinearLayout parent,JSONObject response) throws JSONException {
        JSONObject data=response.getJSONObject("payload").getJSONObject("data");
        JSONObject values=data.optJSONObject("module_data"); List<ModuleSlots.Slot> slots=slots(data);
        boolean fresh=response.optBoolean("fresh");
        LinearLayout summary=card(parent);
        summary.addView(label(fresh?"● 정상 수신":"● 오래된 데이터 · 현재 상태 확인 필요",14,fresh?GREEN:AMBER));
        long count=slots.stream().filter(s->s.mapped).count();
        summary.addView(label("배터리 모듈  "+count+" / 10",24,INK));
        rackSummary(summary,data,slots,fresh);
        summary.addView(label("측정  "+data.optString("last_poll_at","—")+"\n수신  "+response.optString("received_at","—"),12,MUTED));
        if(slots.isEmpty()) { summary.addView(label("등록된 모듈 정보가 없습니다.",16,AMBER)); return; }
        if(count>10) summary.addView(label("지원 수량(10개)을 초과한 데이터입니다. 서버 구성을 확인하세요.",14,AMBER));
        if(slots.stream().anyMatch(s->!s.mapped)) summary.addView(label("모듈 번호를 확인할 수 없는 측정 행이 있습니다. 미매핑 행으로 별도 표시합니다.",13,AMBER));
        LinearLayout selection=new LinearLayout(context); selection.setOrientation(LinearLayout.VERTICAL);
        LinearLayout rackCard=card(parent); rackCard.addView(label("RACK OVERVIEW",12,GREEN));
        rackCard.addView(label("모듈을 선택해 상세값을 확인하세요",15,INK));
        rackCard.addView(label("번호순 표시 · 실제 장착 위치와 다를 수 있음",11,MUTED));
        List<ModuleSlots.Slot> installed=new ArrayList<>(); for(ModuleSlots.Slot s:slots) if(s.mapped&&installed.size()<10) installed.add(s);
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
        LinearLayout alarm=card(parent); alarm.addView(label("장비 알람",18,INK));
        Object a=data.opt("active_alarms"); alarm.addView(label(a==null||a==JSONObject.NULL?"정보 없음":a.toString(),14,MUTED));
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
    private void rackSummary(LinearLayout parent,JSONObject data,List<ModuleSlots.Slot> slots,boolean fresh) {
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
    }
    private void showModule(LinearLayout parent,ModuleSlots.Slot slot,JSONObject m,boolean fresh) {
        parent.removeAllViews(); LinearLayout box=card(parent);
        box.addView(label(slot.label(),23,INK));
        if(!fresh) box.addView(label("이전 수신값 · 현재 정상 값으로 사용하지 마세요",13,AMBER));
        if(m==null) { box.addView(label("이 모듈의 측정 데이터가 없습니다.",15,AMBER)); return; }
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
