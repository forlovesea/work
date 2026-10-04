package com.remotecontrol;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.*;

/** TLS relay transport. Screen/control traffic inside this tunnel has its own pinned TLS session. */
public final class Relay {
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
        try (ServerSocket listener = new ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))) {
            Socket client = new Socket("127.0.0.1", listener.getLocalPort());
            try { Socket peer = listener.accept(); bridge(relay, peer); return client; }
            catch (IOException e) { client.close(); throw e; }
        }
    }
    public static void bridge(Socket left, Socket right) {
        copy(left, right); copy(right, left);
    }
    private static void copy(Socket from, Socket to) {
        new Thread(() -> {
            try {
                byte[] buffer = new byte[16384]; int size;
                InputStream input = from.getInputStream(); OutputStream output = to.getOutputStream();
                while ((size = input.read(buffer)) != -1) { output.write(buffer, 0, size); output.flush(); }
            } catch (IOException ignored) {
            } finally {
                try { from.close(); } catch (IOException ignored) {}
                try { to.close(); } catch (IOException ignored) {}
            }
        }, "relay-pump").start();
    }
}
