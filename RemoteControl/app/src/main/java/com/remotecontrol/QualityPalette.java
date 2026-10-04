package com.remotecontrol;

/** Opaque colors with readable foregrounds; severity is also shown as text. */
public final class QualityPalette {
    private QualityPalette() {}
    public static final int[] BACKGROUNDS = {
        0xffdcfce7, 0xff86efac, 0xfffef9c3, 0xfffde047, 0xffffedd5,
        0xfffdba74, 0xffc2410c, 0xfffecaca, 0xffdc2626, 0xff7f1d1d
    };
    public static final String[] LABELS = {
        "매우 원활", "원활", "약간의 지연", "지연이 느껴짐", "반응이 느림",
        "느림 · 끊김 주의", "매우 느림 · 불안정", "심한 지연 · 끊김 의심", "응답 중단", "장시간 응답 없음"
    };
    public static int foreground(int level) { return level == 6 || level >= 8 ? 0xffffffff : 0xff172033; }
}
