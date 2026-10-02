package com.batterywatch.monitor;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Locale;

/** Convert wire timestamps to the phone timezone, including the date boundary. */
final class DisplayTime {
    private static final DateTimeFormatter FORMAT =
        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss 'UTC'xxx", Locale.ROOT);
    static String format(String value) { return format(value, ZoneId.systemDefault()); }
    static String format(String value, ZoneId zone) {
        if (value == null || value.trim().isEmpty() || value.equals("null")) return "—";
        try { return FORMAT.format(OffsetDateTime.parse(value).atZoneSameInstant(zone)); }
        catch (DateTimeParseException e) { return "시각 형식 확인 필요"; }
    }
    static String epoch(double seconds) {
        if (!Double.isFinite(seconds)) return "—";
        return FORMAT.format(Instant.ofEpochMilli((long)(seconds * 1000)).atZone(ZoneId.systemDefault()));
    }
    static String age(double seconds) {
        if (!Double.isFinite(seconds)) return "측정 시각 없음";
        if (seconds < 0) return "측정 시각이 서버보다 " + (long)Math.ceil(-seconds) + "초 앞섬 · PC/서버 시계 확인";
        long n = (long) seconds;
        if (n < 60) return n + "초 전 측정";
        if (n < 3600) return n / 60 + "분 " + n % 60 + "초 전 측정";
        if (n < 86400) return n / 3600 + "시간 " + n % 3600 / 60 + "분 전 측정";
        return n / 86400 + "일 " + n % 86400 / 3600 + "시간 전 측정";
    }
}
