package com.remotecontrol;

import org.junit.Test;
import static org.junit.Assert.*;
import static com.remotecontrol.ConnectionHealth.State.*;

public class ConnectionHealthTest {
    private ConnectionHealth ready(boolean allowed, boolean controlReady) {
        ConnectionHealth health = new ConnectionHealth();
        health.connected(1000); health.sent(1000); health.pong(1000, 1100, allowed, controlReady); health.frame();
        return health;
    }
    @Test public void requiresTargetReplyAndScreenBeforeGreen() {
        ConnectionHealth health = new ConnectionHealth();
        assertEquals(IDLE, health.state(0));
        health.connecting(); assertEquals(CONNECTING, health.state(0));
        health.connected(1000); health.frame(); assertEquals(CHECKING, health.state(1100));
        health.sent(1100); assertTrue(health.pong(1100, 1200, true, true));
        assertEquals(GOOD, health.state(1200)); assertTrue(health.canSendControl(1200));
        health.connected(2000); health.sent(2000); health.pong(2000, 2100, true, true);
        assertEquals(CHECKING, health.state(2100)); assertFalse(health.canSendControl(2100));
    }
    @Test public void distinguishesViewOnlyFromLostPermission() {
        assertEquals(VIEW_ONLY, ready(false, false).state(1100));
        assertEquals(CONTROL_UNAVAILABLE, ready(true, false).state(1100));
        assertFalse(ready(false, true).canSendControl(1100));
    }
    @Test public void silenceProgressesToWarningRedAndTimeout() {
        ConnectionHealth health = ready(true, true);
        assertEquals(GOOD, health.state(3599));
        assertEquals(DELAYED, health.state(3600));
        assertEquals(UNRESPONSIVE, health.state(6100));
        assertFalse(health.canSendControl(6100));
        assertFalse(health.timedOut(11099)); assertTrue(health.timedOut(11100));
    }
    @Test public void slowReplyRecoversAfterFreshFastReply() {
        ConnectionHealth health = ready(true, true);
        health.sent(2000); health.pong(2000, 2700, true, true);
        assertEquals(DELAYED, health.state(2700)); assertEquals(700, health.rtt());
        health.sent(3000); health.pong(3000, 3100, true, true);
        assertEquals(GOOD, health.state(3100));
    }
    @Test public void onlyOneProbeInFlightAndNoUnsolicitedReplies() {
        ConnectionHealth health = new ConnectionHealth(); health.connected(1000);
        assertFalse(health.pong(1000, 1100, true, true));
        assertTrue(health.needsPing(1000)); health.sent(1000);
        assertFalse(health.needsPing(3000)); assertFalse(health.pong(999, 1100, true, true));
        assertTrue(health.pong(1000, 1100, true, true));
        assertFalse(health.pong(1000, 1200, true, true));
        assertFalse(health.needsPing(1999)); assertTrue(health.needsPing(2000));
    }
    @Test public void permissionChangesAreReflectedWithoutReconnect() {
        ConnectionHealth health = ready(true, true);
        health.sent(2000); health.pong(2000, 2100, true, false);
        assertEquals(CONTROL_UNAVAILABLE, health.state(2100)); assertFalse(health.canSendControl(2100));
        health.sent(3000); health.pong(3000, 3100, true, true);
        assertEquals(GOOD, health.state(3100));
    }
    @Test public void unchangedScreenDoesNotImplyConnectionFailure() {
        ConnectionHealth health = ready(true, true);
        for (int now = 2000; now <= 20000; now += 1000) {
            health.sent(now); health.pong(now, now + 50, true, true);
            assertEquals(GOOD, health.state(now + 50));
        }
    }
    @Test public void disconnectClearsOldSessionAndLateReply() {
        ConnectionHealth health = ready(true, true); health.sent(2000);
        health.disconnected(true); assertEquals(DISCONNECTED, health.state(2100));
        assertFalse(health.pong(2000, 2100, true, true)); assertFalse(health.canSendControl(2100));
        health.connected(3000); assertEquals(CHECKING, health.state(3000)); assertEquals(-1, health.rtt());
        health.disconnected(false); assertEquals(IDLE, health.state(3100));
    }
    @Test public void latencyUsesEightFineGrainedBands() {
        long[] latencies = {99, 100, 200, 350, 500, 700, 1000, 1500};
        for (int level = 0; level < latencies.length; level++) {
            ConnectionHealth health = new ConnectionHealth(); health.connected(1000); health.sent(1000);
            health.pong(1000, 1000 + latencies[level], true, true); health.frame();
            assertEquals(level, health.qualityLevel(1000 + latencies[level]));
        }
    }
    @Test public void silenceDeepensRedAndDisconnectKeepsDarkRed() {
        ConnectionHealth health = ready(true, true);
        assertEquals(8, health.qualityLevel(6100)); assertEquals(9, health.qualityLevel(9100));
        health.disconnected(true); assertEquals(9, health.qualityLevel(9200));
        health.disconnected(false); assertEquals(-1, health.qualityLevel(9300));
    }
    @Test public void outstandingProbeShowsDegradationBeforeReply() {
        ConnectionHealth health = ready(true, true); health.sent(2000);
        assertEquals(5, health.qualityLevel(2700));
    }
    @Test public void fastLatestReplyDoesNotHideRepeatedStutters() {
        ConnectionHealth health = new ConnectionHealth(); health.connected(1000); health.frame();
        long[] values = {900, 50, 900, 50};
        for (int i = 0; i < values.length; i++) {
            long sent = 1000 + i * 1000; health.sent(sent); health.pong(sent, sent + values[i], true, true);
        }
        assertEquals(850, health.jitter()); assertEquals(50, health.latePercent());
        assertEquals(7, health.qualityLevel(4050));
    }
    @Test public void slidingWindowRecoversAndReconnectClearsStatistics() {
        ConnectionHealth health = new ConnectionHealth(); health.connected(1000);
        health.sent(1000); health.pong(1000, 1900, true, true);
        for (int i = 2; i <= 11; i++) { health.sent(i * 1000); health.pong(i * 1000, i * 1000 + 50, true, true); }
        assertEquals(10, health.sampleCount()); assertEquals(0, health.jitter()); assertEquals(0, health.latePercent());
        assertEquals(0, health.qualityLevel(11050));
        health.connected(12000); assertEquals(0, health.sampleCount()); assertEquals(0, health.jitter());
    }
    @Test public void paletteHasDistinctShadeForEveryLevel() {
        assertEquals(10, QualityPalette.BACKGROUNDS.length);
        assertEquals(10, QualityPalette.LABELS.length);
        java.util.Set<Integer> colors = new java.util.HashSet<>();
        for (int color : QualityPalette.BACKGROUNDS) colors.add(color);
        assertEquals(10, colors.size());
    }
}
