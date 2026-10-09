package com.remotecontrol;

import org.junit.Test;
import java.io.*;
import java.net.Socket;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.Assert.*;

public class RelayTest {
    private static class MemorySocket extends Socket {
        final InputStream input;
        final ByteArrayOutputStream output = new ByteArrayOutputStream();
        MemorySocket(InputStream input) { this.input = input; }
        @Override public InputStream getInputStream() { return input; }
        @Override public OutputStream getOutputStream() { return output; }
    }
    @Test public void recordsDirectionCountsAndOnlyOneFirstEndWithoutPayload() throws Exception {
        MemorySocket relay = new MemorySocket(new ByteArrayInputStream(new byte[]{11, 12, 13}));
        IOException failure = new IOException("simulated read failure");
        MemorySocket local = new MemorySocket(new InputStream() {
            @Override public int read() throws IOException { throw failure; }
        });
        List<String> events = Collections.synchronizedList(new ArrayList<>());
        List<Throwable> errors = Collections.synchronizedList(new ArrayList<>());
        CountDownLatch ended = new CountDownLatch(2);
        Relay.bridge(relay, local, (event, error) -> {
            events.add(event);
            if (error != null) errors.add(error);
            if (event.contains(" ended ")) ended.countDown();
        });
        assertTrue(ended.await(5, TimeUnit.SECONDS));
        assertArrayEquals(new byte[]{11, 12, 13}, local.output.toByteArray());
        assertEquals(1, events.stream().filter(e -> e.contains("ended first=true")).count());
        assertTrue(events.stream().anyMatch(e -> e.contains("direction=relay-to-local") && e.contains("received=3 forwarded=3")));
        assertTrue(events.stream().anyMatch(e -> e.contains("direction=local-to-relay") && e.contains("reason=IOException phase=read")));
        assertEquals(Collections.singletonList(failure), errors);
    }
}
