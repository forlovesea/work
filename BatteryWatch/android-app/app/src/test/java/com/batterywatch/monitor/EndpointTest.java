package com.batterywatch.monitor;
import org.junit.Test;
import static org.junit.Assert.*;
public class EndpointTest {
    @Test public void productionRequiresHttps() {
        assertEquals("https://example.org:8443", Endpoint.validate("https://example.org:8443/", false));
        for (String value : new String[]{"http://example.org", "https://user:secret@example.org", "https://example.org/path", "https://example.org?token=x", "https://example.org:0"}) {
            try { Endpoint.validate(value, false); fail(value); } catch (IllegalArgumentException expected) {}
        }
    }
    @Test public void debugHttpIsLocalOnly() {
        assertEquals("http://10.0.2.2:8443", Endpoint.validate("http://10.0.2.2:8443", true));
        try { Endpoint.validate("http://192.168.1.2:8443", true); fail(); } catch (IllegalArgumentException expected) {}
    }
}
