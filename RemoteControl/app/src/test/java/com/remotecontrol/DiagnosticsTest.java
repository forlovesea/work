package com.remotecontrol;

import org.junit.Test;
import static org.junit.Assert.*;

public class DiagnosticsTest {
    @Test public void redactsCredentialsAndSessionTokens() {
        String accessKey = "a".repeat(64);
        String sessionToken = "b".repeat(32);

        String sanitized = Diagnostics.sanitize(
                "key=" + accessKey + " token: " + sessionToken
                        + " secret='not-hex-secret-value' handshake failed");

        assertFalse(sanitized.contains(accessKey));
        assertFalse(sanitized.contains(sessionToken));
        assertFalse(sanitized.contains("not-hex-secret-value"));
        assertTrue(sanitized.contains("handshake failed"));
    }

    @Test public void flattensMultilineExceptionMessages() {
        assertEquals("first second third", Diagnostics.sanitize("first\r\nsecond\tthird"));
    }
}
