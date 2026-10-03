package com.batterywatch.monitor;

import java.util.Locale;
import java.util.LinkedHashSet;
import java.util.Set;

/** Formatting and cell-temperature extrema without assuming rack wiring. */
public final class RackSummary {
    private RackSummary() {}
    public static String number(Object value, boolean percent) {
        return number(value, percent, 1);
    }
    public static String number(Object value, boolean percent, int decimals) {
        if(value==null) return "—";
        try {
            double n=Double.parseDouble(value.toString().trim().replace("%", "").trim());
            if(!Double.isFinite(n)||(percent&&(n<0||n>100))||decimals<0||decimals>6) return "—";
            return String.format(Locale.ROOT,"%."+decimals+"f",n);
        } catch(NumberFormatException e) { return "—"; }
    }
    public static String protection(Object value) {
        if(Boolean.TRUE.equals(value)||"발생".equals(value)) return "발생";
        if(Boolean.FALSE.equals(value)||"정상".equals(value)) return "정상";
        return "—";
    }
    public static String communicationStatus(Object value) {
        if(value==null) return "—";
        String status=value.toString().trim();
        switch(status) {
            case "0": case "Online": return "Online";
            case "1": case "Offline": return "Offline";
            case "2": case "Sleep": return "Sleep";
            case "3": case "Disconnect": return "Disconnect";
            case "4": case "충전중": return "충전중";
            case "5": case "방전중": return "방전중";
            case "6": case "Standby": return "Standby";
            case "255": case "Unknown": return "Unknown";
            default: return "—";
        }
    }
    public static final class Temperatures {
        private double min=Double.POSITIVE_INFINITY,max=Double.NEGATIVE_INFINITY;
        private final Set<String> lows=new LinkedHashSet<>(),highs=new LinkedHashSet<>();
        public void add(String module,double value) {
            if(!Double.isFinite(value)) return;
            if(value<min) { min=value; lows.clear(); }
            if(value==min) lows.add(module);
            if(value>max) { max=value; highs.clear(); }
            if(value==max) highs.add(module);
        }
        public String minimum() { return number(min,false); }
        public String maximum() { return number(max,false); }
        public String minModules() { return lows.isEmpty()?"모듈 정보 없음":String.join(", ",lows); }
        public String maxModules() { return highs.isEmpty()?"모듈 정보 없음":String.join(", ",highs); }
    }
}
