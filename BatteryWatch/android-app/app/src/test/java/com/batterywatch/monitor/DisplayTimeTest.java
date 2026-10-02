package com.batterywatch.monitor;
import org.junit.Test;
import java.time.ZoneId;
import static org.junit.Assert.*;
public class DisplayTimeTest {
    @Test public void utcPreviousDayBecomesCurrentKoreanDate() {
        assertEquals("2026-10-03 01:20:30 UTC+09:00",
            DisplayTime.format("2026-10-02T16:20:30.123456+00:00", ZoneId.of("Asia/Seoul")));
    }
    @Test public void equivalentOffsetsShowSameTime() {
        ZoneId zone=ZoneId.of("Asia/Seoul");
        assertEquals(DisplayTime.format("2026-10-02T16:20:30Z",zone),
            DisplayTime.format("2026-10-03T01:20:30+09:00",zone));
    }
    @Test public void phoneTimezoneObservesDaylightSaving() {
        assertEquals("2026-07-01 08:00:00 UTC-04:00",
            DisplayTime.format("2026-07-01T12:00:00Z",ZoneId.of("America/New_York")));
    }
    @Test public void missingOrInvalidTimesAreNotPresentedAsCurrent() {
        assertEquals("—",DisplayTime.format(null));
        assertEquals("—",DisplayTime.format("null"));
        assertEquals("시각 형식 확인 필요",DisplayTime.format("2026-10-02T16:20:30"));
    }
    @Test public void ageDistinguishesClockSkewAndStaleMeasurements() {
        assertTrue(DisplayTime.age(-5).contains("시계 확인"));
        assertEquals("측정 시각 없음",DisplayTime.age(Double.NaN));
        assertEquals("1분 5초 전 측정",DisplayTime.age(65));
        assertEquals("1일 1시간 전 측정",DisplayTime.age(90000));
    }
}
