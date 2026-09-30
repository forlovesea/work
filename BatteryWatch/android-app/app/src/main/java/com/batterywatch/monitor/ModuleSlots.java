package com.batterywatch.monitor;

import java.util.*;

/** Module IDs are not SNMP row indexes. Keep missing and unmapped rows explicit. */
public final class ModuleSlots {
    private ModuleSlots() {}
    public static final class Slot {
        public final String id, row;
        public final boolean mapped;
        Slot(String id, String row, boolean mapped) { this.id=id; this.row=row; this.mapped=mapped; }
        public String label() { return mapped ? "모듈 " + id : "미매핑 행 " + row; }
    }
    public static List<Slot> resolve(Map<String,String> mapping, Set<String> rows) {
        List<Slot> result=new ArrayList<>();
        Set<String> used=new HashSet<>();
        List<String> ids=new ArrayList<>(mapping.keySet()); ids.sort(ModuleSlots::compare);
        for(String id:ids) {
            String row=mapping.get(id);
            result.add(new Slot(id,row,true));
            if(row!=null) used.add(row);
        }
        List<String> rest=new ArrayList<>(rows); rest.removeAll(used); rest.sort(ModuleSlots::compare);
        for(String row:rest) result.add(new Slot(row,row,false));
        return result;
    }
    private static int compare(String a,String b) {
        try { int n=Long.compare(Long.parseLong(a),Long.parseLong(b)); return n!=0?n:a.compareTo(b); }
        catch(NumberFormatException e) { return a.compareTo(b); }
    }
}
