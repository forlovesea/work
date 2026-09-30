package com.batterywatch.monitor;

import java.util.Locale;
import java.util.LinkedHashSet;
import java.util.Set;

/** Formatting and cell-temperature extrema without assuming rack wiring. */
public final class RackSummary {
    private RackSummary() {}
    public static String number(Object value, boolean percent) {
        if(value==null) return "—";
        try {
            double n=Double.parseDouble(value.toString().trim().replace("%", "").trim());
            if(!Double.isFinite(n)||(percent&&(n<0||n>100))) return "—";
            return String.format(Locale.ROOT,"%.1f",n);
        } catch(NumberFormatException e) { return "—"; }
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
