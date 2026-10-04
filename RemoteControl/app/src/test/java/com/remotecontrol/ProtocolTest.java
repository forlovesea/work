package com.remotecontrol;

import org.junit.Test;
import static org.junit.Assert.*;

public class ProtocolTest {
    @Test public void validInvitation() {
        for (int port : new int[]{55000, 57500, 60000}) {
            String value = "RC2|relay.example.com|" + port + "|" + "ef".repeat(16) + "|" + "ab".repeat(32) + "|" + "cd".repeat(16) + "|" + Protocol.WIRE_VERSION;
            assertEquals("relay.example.com", Protocol.invitation(value)[1]);
        }
    }
    @Test public void rejectsMalformedInvitations() {
        for (String value : new String[]{"", "RC1|localhost|abc|def", "RC2|ip|" + "ab".repeat(32) + "|" + "cd".repeat(16),
                "RC1||" + "ab".repeat(32) + "|" + "cd".repeat(16)}) {
            try { Protocol.invitation(value); fail("accepted invalid invitation"); }
            catch (IllegalArgumentException expected) {}
        }
    }
    @Test public void rejectsInvalidGestureCoordinates() {
        assertTrue(Protocol.coordinate(0)); assertTrue(Protocol.coordinate(1));
        assertFalse(Protocol.coordinate(Float.NaN)); assertFalse(Protocol.coordinate(Float.POSITIVE_INFINITY));
        assertFalse(Protocol.coordinate(-0.01f)); assertFalse(Protocol.coordinate(1.01f));
    }
    @Test public void rejectsInvalidRelayPortAndKey() {
        String suffix = "|" + "ab".repeat(16) + "|" + "cd".repeat(32) + "|" + "ef".repeat(16) + "|" + Protocol.WIRE_VERSION;
        for (String port : new String[]{"0", "80", "443", "54999", "60001", "65536", "-1", "55000x", "999999999999"}) {
            try { Protocol.invitation("RC2|relay.example.com|" + port + suffix); fail("invalid port accepted"); }
            catch (IllegalArgumentException expected) {}
        }
    }
    @Test public void rejectsPreHeartbeatVersion() {
        String old = "RC2|relay.example.com|55000|" + "ab".repeat(16) + "|" + "cd".repeat(32) + "|" + "ef".repeat(16) + "|1";
        try { Protocol.invitation(old); fail("old protocol accepted"); }
        catch (IllegalArgumentException expected) {}
    }
}
