package com.batterywatch.monitor;

import org.junit.Test;
import java.util.*;
import static org.junit.Assert.*;

public class ModuleSlotsTest {
    @Test public void oneModuleUsesMappedMeasurementRow() {
        List<ModuleSlots.Slot> slots=ModuleSlots.resolve(Collections.singletonMap("7","42"),Collections.singleton("42"));
        assertEquals(1,slots.size()); assertEquals("7",slots.get(0).id); assertEquals("42",slots.get(0).row); assertTrue(slots.get(0).mapped);
    }
    @Test public void tenModulesSortNumericallyAndKeepRowMapping() {
        Map<String,String> map=new HashMap<>(); Set<String> rows=new HashSet<>();
        for(int i=10;i>=1;i--){map.put(""+i,""+(100+i));rows.add(""+(100+i));}
        List<ModuleSlots.Slot> slots=ModuleSlots.resolve(map,rows);assertEquals(10,slots.size());
        for(int i=0;i<10;i++){assertEquals(""+(i+1),slots.get(i).id);assertEquals(""+(101+i),slots.get(i).row);}
    }
    @Test public void missingMappingNeverInventsModuleIdentity() {
        List<ModuleSlots.Slot> slots=ModuleSlots.resolve(Collections.emptyMap(),Collections.singleton("42"));
        assertFalse(slots.get(0).mapped);assertEquals("미매핑 행 42",slots.get(0).label());
    }
    @Test public void missingMeasurementAndUnmappedRowRemainVisible() {
        Map<String,String> map=new HashMap<>();map.put("2",null);map.put("5","9");
        List<ModuleSlots.Slot> slots=ModuleSlots.resolve(map,Collections.singleton("88"));
        assertEquals(3,slots.size());assertNull(slots.get(0).row);assertEquals("9",slots.get(1).row);assertFalse(slots.get(2).mapped);
    }
    @Test public void emptyAndExcessDataAreNotSilentlyFabricatedOrDiscarded() {
        assertTrue(ModuleSlots.resolve(Collections.emptyMap(),Collections.emptySet()).isEmpty());
        Map<String,String> map=new HashMap<>();for(int i=1;i<=11;i++)map.put(""+i,""+i);
        assertEquals(11,ModuleSlots.resolve(map,Collections.emptySet()).size());
    }
}
