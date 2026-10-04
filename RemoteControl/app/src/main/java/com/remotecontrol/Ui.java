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
}
