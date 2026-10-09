package com.remotecontrol;

import android.app.Activity;
import android.graphics.Color;
import android.view.View;
import android.widget.*;

public final class Ui {
    public static LinearLayout page(Activity activity, String title) {
        return page(activity, title, false);
    }
    public static LinearLayout page(Activity activity, String title, boolean scrollable) {
        LinearLayout layout = new LinearLayout(activity);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(24, 24, 24, 12);
        layout.setBackgroundColor(Color.rgb(242, 246, 250));
        // Apply system-bar insets for Android 15 edge-to-edge enforcement.
        layout.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(24 + insets.getSystemWindowInsetLeft(), 20 + insets.getSystemWindowInsetTop(),
                    24 + insets.getSystemWindowInsetRight(), 12 + insets.getSystemWindowInsetBottom());
            return insets;
        });
        if (scrollable) {
            ScrollView scroll = new ScrollView(activity); scroll.setFillViewport(true); scroll.addView(layout);
            activity.setContentView(scroll);
        } else activity.setContentView(layout);
        TextView heading = text(activity, layout, title);
        heading.setTextSize(25);
        try {
            String version = activity.getPackageManager().getPackageInfo(activity.getPackageName(), 0).versionName;
            if (version != null && !version.isEmpty()) {
                int separator = title.indexOf(" \u00b7 ");
                int insertAt = separator >= 0 ? separator : title.length();
                android.text.SpannableStringBuilder label = new android.text.SpannableStringBuilder(title);
                String suffix = "\u00a0v" + version;
                label.insert(insertAt, suffix);
                label.setSpan(new android.text.style.RelativeSizeSpan(0.56f), insertAt, insertAt + suffix.length(),
                        android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                label.setSpan(new android.text.style.ForegroundColorSpan(Color.rgb(85, 99, 115)),
                        insertAt, insertAt + suffix.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                heading.setText(label);
            }
        } catch (android.content.pm.PackageManager.NameNotFoundException ignored) {
            // Keep the title usable if package metadata is unavailable.
        }
        return layout;
    }
    public static TextView text(Activity a, LinearLayout parent, String value) {
        TextView view = new TextView(a); view.setText(value); view.setTextSize(15);
        view.setPadding(0, 10, 0, 10); parent.addView(view); return view;
    }
    public static Button button(Activity a, LinearLayout parent, String label, View.OnClickListener click) {
        Button button = new Button(a); button.setText(label); button.setOnClickListener(click);
        parent.addView(button); return button;
    }
    public static void headerAction(Activity activity, LinearLayout page, String label, View.OnClickListener click) {
        TextView title = (TextView) page.getChildAt(0);
        page.removeViewAt(0);
        LinearLayout header = new LinearLayout(activity);
        header.setGravity(android.view.Gravity.CENTER_VERTICAL);
        header.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button action = new Button(activity);
        action.setText(label);
        action.setTextSize(12);
        action.setMinWidth(0);
        action.setPadding(8, 0, 8, 0);
        action.setOnClickListener(click);
        header.addView(action);
        page.addView(header, 0);
    }
}
