package com.batterywatch.monitor;
import org.junit.Test;
import static org.junit.Assert.*;

public class RackSummaryTest {
    @Test public void temperaturesIncludeTiesAndIgnoreMissing() {
        RackSummary.Temperatures t=new RackSummary.Temperatures();
        assertEquals("—",t.maximum());
        t.add("모듈 1",-5); t.add("모듈 2",32); t.add("모듈 3",32);
        t.add("모듈 4",Double.NaN); t.add("모듈 4",Double.POSITIVE_INFINITY);
        assertEquals("-5.0",t.minimum()); assertEquals("32.0",t.maximum());
        assertEquals("모듈 1",t.minModules()); assertEquals("모듈 2, 모듈 3",t.maxModules());
    }
    @Test public void numbersPreserveZeroAndRejectInvalidPercentages() {
        assertEquals("0.0",RackSummary.number(0,true));
        assertEquals("82.0",RackSummary.number("82 %",true));
        assertEquals("0.45",RackSummary.number(0.45,false,2));
        assertEquals("—",RackSummary.number(101,true));
        assertEquals("—",RackSummary.number("-",false));
        assertEquals("—",RackSummary.number(null,false));
        assertEquals("-4.2",RackSummary.number(-4.2,false));
    }
    @Test public void protectionStatusKeepsUnknownDistinctFromNormal() {
        assertEquals("발생",RackSummary.protection(true));
        assertEquals("정상",RackSummary.protection(false));
        assertEquals("발생",RackSummary.protection("발생"));
        assertEquals("—",RackSummary.protection(null));
        assertEquals("—",RackSummary.protection("-"));
    }
    @Test public void moduleCommunicationStatusSupportsCodesAndLabels() {
        assertEquals("Online",RackSummary.communicationStatus(0));
        assertEquals("Offline",RackSummary.communicationStatus("1"));
        assertEquals("Disconnect",RackSummary.communicationStatus("Disconnect"));
        assertEquals("충전중",RackSummary.communicationStatus(4));
        assertEquals("Unknown",RackSummary.communicationStatus(255));
        assertEquals("—",RackSummary.communicationStatus(null));
        assertEquals("—",RackSummary.communicationStatus("unexpected"));
    }
}
