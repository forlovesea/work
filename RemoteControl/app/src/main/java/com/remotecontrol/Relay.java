package com.remotecontrol;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.*;

/** TLS relay transport. Screen/control traffic inside this tunnel has its own pinned TLS session. */
public final class Relay {
    public interface Trace { void record(String event, Throwable error); }
    private static final Trace SILENT = (event, error) -> {};
    private static final java.util.concurrent.atomic.AtomicLong BRIDGES = new java.util.concurrent.atomic.AtomicLong();
    public static SSLSocket socket() throws IOException {
        return (SSLSocket) SSLSocketFactory.getDefault().createSocket();
    }
    public static void register(SSLSocket socket, String host, int port, String role, String room) throws IOException {
        if (!Protocol.relayPort(port)) throw new IOException("중계 포트는 55000~60000이어야 합니다.");
        socket.connect(new InetSocketAddress(host, port), 10000);
        SSLParameters parameters = socket.getSSLParameters();
        parameters.setEndpointIdentificationAlgorithm("HTTPS"); socket.setSSLParameters(parameters);
        socket.setSoTimeout(15000); socket.startHandshake();
        socket.getOutputStream().write((role + " " + room + "\n").getBytes(StandardCharsets.US_ASCII));
        socket.getOutputStream().flush();
        String expected = role.equals("TARGET") ? "READY" : "PAIRED";
        if (!line(socket).equals(expected)) throw new IOException("중계서버가 연결을 거부했습니다.");
    }
    public static String line(Socket socket) throws IOException {
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < 128; i++) {
            int next = socket.getInputStream().read();
            if (next == -1) throw new EOFException();
            if (next == '\n') return result.toString();
            result.append((char) next);
        }
        throw new IOException("Invalid relay response");
    }
    public static Socket localTunnel(Socket relay) throws IOException {
        return localTunnel(relay, SILENT);
    }
    public static Socket localTunnel(Socket relay, Trace trace) throws IOException {
        try (ServerSocket listener = new ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))) {
            Socket client = new Socket("127.0.0.1", listener.getLocalPort());
            try { Socket peer = listener.accept(); bridge(relay, peer, trace); return client; }
            catch (IOException e) { client.close(); throw e; }
        }
    }
    public static void bridge(Socket left, Socket right) {
        bridge(left, right, SILENT);
    }
    public static void bridge(Socket left, Socket right, Trace trace) {
        String id = "bridge=" + BRIDGES.incrementAndGet();
        java.util.concurrent.atomic.AtomicBoolean ended = new java.util.concurrent.atomic.AtomicBoolean();
        trace.record(id + " started", null);
        copy(left, right, trace, id + " direction=relay-to-local", ended);
        copy(right, left, trace, id + " direction=local-to-relay", ended);
    }
    private static void copy(Socket from, Socket to, Trace trace, String label,
                             java.util.concurrent.atomic.AtomicBoolean ended) {
        new Thread(() -> {
            long started = System.nanoTime(), received = 0, forwarded = 0;
            String phase = "open-streams", reason = "EOF";
            IOException failure = null;
            try {
                byte[] buffer = new byte[16384]; int size;
                InputStream input = from.getInputStream(); OutputStream output = to.getOutputStream();
                while (true) {
                    phase = "read"; size = input.read(buffer);
                    if (size == -1) break;
                    received += size;
                    if (received == size) trace.record(label + " first-read bytes=" + size, null);
                    phase = "write"; output.write(buffer, 0, size);
                    phase = "flush"; output.flush(); forwarded += size;
                }
            } catch (IOException error) {
                reason = "IOException"; failure = error;
            } finally {
                boolean first = ended.compareAndSet(false, true);
                trace.record(label + " ended first=" + first + " reason=" + reason + " phase=" + phase
                        + " received=" + received + " forwarded=" + forwarded
                        + " elapsedMs=" + (System.nanoTime() - started) / 1000000
                        + " fromClosed=" + from.isClosed() + " toClosed=" + to.isClosed(), failure);
                try { from.close(); } catch (IOException ignored) {}
                try { to.close(); } catch (IOException ignored) {}
            }
        }, "relay-pump").start();
    }
}
