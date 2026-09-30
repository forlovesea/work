package com.batterywatch.monitor;

import android.app.Activity;
import android.app.Dialog;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.text.InputType;
import android.text.method.PasswordTransformationMethod;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import java.util.ArrayList;
import java.util.List;

/** Scrollable connection form with persistent labels and field-local validation. */
final class ConnectionSettingsDialog extends Dialog {
    interface SaveListener {
        void save(String url, String token, int seconds, boolean logout, ConnectionSettingsDialog dialog);
    }
    private final BatteryDashboard ui;
    private final SaveListener listener;
    private final List<View> controls=new ArrayList<>();
    private EditText url, token, interval;
    private TextView urlError, tokenError, intervalError, feedback;
    private Button save;

    ConnectionSettingsDialog(Activity activity, SettingsStore settings, SaveListener listener) {
        super(activity); this.listener=listener; ui=new BatteryDashboard(activity);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout root=vertical(); root.setPadding(ui.dp(20),ui.dp(16),ui.dp(20),ui.dp(12));
        root.setBackgroundColor(BatteryDashboard.BG);
        root.addView(ui.label("BATTERYWATCH  /  CONNECTION",11,BatteryDashboard.GREEN));
        root.addView(ui.label("서버 연결 설정",26,BatteryDashboard.INK));
        root.addView(ui.label("배터리 데이터를 조회할 서버를 연결하세요.",14,BatteryDashboard.MUTED));
        ScrollView scroll=new ScrollView(activity);scroll.setClipToPadding(false);
        LinearLayout form=vertical();form.setPadding(0,ui.dp(8),0,ui.dp(12));
        scroll.addView(form);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));

        LinearLayout server=ui.card(form);
        server.addView(ui.label("01  서버 주소",18,BatteryDashboard.INK));
        server.addView(ui.label("HTTPS 주소와 앱 조회 포트를 입력하세요.",13,BatteryDashboard.MUTED));
        url=input(server,"https://battery.example.com:8443",InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
        url.setText(settings.url());urlError=error(server);
        server.addView(ui.label("앱 조회 기본 포트는 8443입니다.\n수집기 업로드 포트 9443과 구분하세요.",13,BatteryDashboard.MUTED));

        LinearLayout credentials=ui.card(form);
        credentials.addView(ui.label("02  조회용 토큰",18,BatteryDashboard.INK));
        credentials.addView(ui.label("서버에서 발급받은 앱 조회용 토큰을 붙여넣으세요. 수집기 업로드 토큰과는 다릅니다.",13,BatteryDashboard.MUTED));
        token=input(credentials,"조회용 토큰 입력",InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
        token.setTypeface(Typeface.MONOSPACE); token.setTransformationMethod(PasswordTransformationMethod.getInstance());
        token.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        tokenError=error(credentials);
        try {token.setText(settings.token());} catch(Exception e) {tokenError.setText("저장된 토큰을 읽지 못했습니다. 다시 입력하세요.");tokenError.setVisibility(View.VISIBLE);}
        CheckBox reveal=new CheckBox(activity);reveal.setText("토큰 표시");reveal.setTextColor(BatteryDashboard.MUTED);
        reveal.setMinHeight(ui.dp(48));reveal.setButtonTintList(ColorStateList.valueOf(BatteryDashboard.GREEN));
        reveal.setOnCheckedChangeListener((b,checked)->{int position=token.getSelectionStart();
            token.setTransformationMethod(checked?null:PasswordTransformationMethod.getInstance());
            token.setSelection(Math.max(0,Math.min(position,token.length())));});
        credentials.addView(reveal);controls.add(reveal);

        LinearLayout timing=ui.card(form);
        timing.addView(ui.label("03  조회 주기",18,BatteryDashboard.INK));
        timing.addView(ui.label("앱 화면을 보고 있을 때 갱신하는 간격입니다.",13,BatteryDashboard.MUTED));
        LinearLayout intervalRow=new LinearLayout(activity);intervalRow.setGravity(Gravity.CENTER_VERTICAL);
        interval=input(intervalRow,"5",InputType.TYPE_CLASS_NUMBER);
        interval.setLayoutParams(new LinearLayout.LayoutParams(0,ui.dp(54),1));
        TextView seconds=ui.label("초",16,BatteryDashboard.INK);seconds.setPadding(ui.dp(12),0,ui.dp(12),0);intervalRow.addView(seconds);
        timing.addView(intervalRow);interval.setText(String.valueOf(settings.interval()));
        interval.setImeOptions(EditorInfo.IME_ACTION_DONE);
        interval.setOnEditorActionListener((v,action,event)->{if(action==EditorInfo.IME_ACTION_DONE){submit();return true;}return false;});
        intervalError=error(timing);
        LinearLayout presets=new LinearLayout(activity);
        for(int n:new int[]{5,10,30,60}) {Button preset=button(n+"초",false,()->{interval.setText(String.valueOf(n));intervalError.setVisibility(View.GONE);});
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,ui.dp(48),1);lp.setMargins(ui.dp(2),ui.dp(6),ui.dp(2),0);presets.addView(preset,lp);}
        timing.addView(presets);timing.addView(ui.label("5~300초 · 기본 5초",12,BatteryDashboard.MUTED));

        LinearLayout delivery=ui.card(form);delivery.addView(ui.label("알림 수신",15,BatteryDashboard.INK));
        delivery.addView(ui.label(PushBridge.description(activity),13,BatteryDashboard.MUTED));
        if(!settings.url().isEmpty()) {Button logout=button("저장된 연결 해제",false,()->listener.save("","",5,true,this));
            logout.setTextColor(BatteryDashboard.AMBER);form.addView(logout,new LinearLayout.LayoutParams(-1,ui.dp(48)));}
        feedback=ui.label("",13,BatteryDashboard.AMBER);feedback.setVisibility(View.GONE);root.addView(feedback);
        save=button("저장하고 조회",true,this::submit);root.addView(save,new LinearLayout.LayoutParams(-1,ui.dp(54)));
        root.addView(button("취소",false,this::dismiss),new LinearLayout.LayoutParams(-1,ui.dp(48)));
        setContentView(root);setCanceledOnTouchOutside(false);
        Window window=getWindow();
        if(window!=null){window.setBackgroundDrawable(new ColorDrawable(BatteryDashboard.BG));
            window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);}
    }
    @Override protected void onStart(){super.onStart();Window w=getWindow();if(w!=null)w.setLayout(-1,-1);}
    private LinearLayout vertical(){LinearLayout l=new LinearLayout(getContext());l.setOrientation(LinearLayout.VERTICAL);return l;}
    private EditText input(LinearLayout parent,String hint,int type){
        EditText field=new EditText(getContext());field.setId(View.generateViewId());field.setInputType(type);field.setSingleLine();
        field.setTextSize(16);field.setTextColor(BatteryDashboard.INK);field.setHintTextColor(BatteryDashboard.MUTED);
        field.setHint(hint);field.setPadding(ui.dp(12),ui.dp(8),ui.dp(12),ui.dp(8));
        GradientDrawable bg=ui.background(BatteryDashboard.BG,10);bg.setStroke(ui.dp(1),0xff455d70);field.setBackground(bg);
        field.setImeOptions(EditorInfo.IME_ACTION_NEXT);
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,ui.dp(54));lp.setMargins(0,ui.dp(10),0,ui.dp(4));
        parent.addView(field,lp);controls.add(field);return field;
    }
    private TextView error(LinearLayout parent){TextView t=ui.label("",13,BatteryDashboard.AMBER);t.setVisibility(View.GONE);
        t.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);parent.addView(t);return t;}
    private Button button(String title,boolean primary,Runnable action){Button b=new Button(getContext());b.setText(title);b.setAllCaps(false);
        b.setTextSize(15);b.setTextColor(primary?BatteryDashboard.BG:BatteryDashboard.GREEN);
        b.setBackgroundTintList(ColorStateList.valueOf(primary?BatteryDashboard.GREEN:BatteryDashboard.PANEL));
        b.setOnClickListener(v->action.run());controls.add(b);return b;}
    private void invalid(EditText field,TextView label,String message){label.setText(message);label.setVisibility(View.VISIBLE);field.requestFocus();}
    private void submit(){
        urlError.setVisibility(View.GONE);tokenError.setVisibility(View.GONE);intervalError.setVisibility(View.GONE);feedback.setVisibility(View.GONE);
        String endpoint;
        try{endpoint=Endpoint.validate(url.getText().toString(),BuildConfig.DEBUG);}
        catch(IllegalArgumentException e){invalid(url,urlError,e.getMessage());return;}
        String secret=token.getText().toString().trim();
        if(secret.isEmpty()){invalid(token,tokenError,"앱 조회용 토큰을 입력하세요.");return;}
        int seconds;
        try{seconds=Integer.parseInt(interval.getText().toString().trim());}
        catch(NumberFormatException e){invalid(interval,intervalError,"조회 주기를 숫자로 입력하세요. (5~300초)");return;}
        if(seconds<5||seconds>300){invalid(interval,intervalError,"5초 이상 300초 이하로 입력하세요.");return;}
        listener.save(endpoint,secret,seconds,false,this);
    }
    void saving(boolean saving){for(View v:controls)v.setEnabled(!saving);setCancelable(!saving);
        save.setText(saving?"설정 적용 중…":"저장하고 조회");if(saving)feedback.setVisibility(View.GONE);}
    void showError(String message){feedback.setText(message);feedback.setVisibility(View.VISIBLE);}
}
