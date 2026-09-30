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
        assertEquals("—",RackSummary.number(101,true));
        assertEquals("—",RackSummary.number("-",false));
        assertEquals("—",RackSummary.number(null,false));
        assertEquals("-4.2",RackSummary.number(-4.2,false));
    }
}
