package com.remotecontrol;

import java.io.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.*;
import org.json.*;

public final class Directory {
    public static JSONObject request(String operation, String key, String device) throws JSONException {
        JSONObject value = new JSONObject().put("op", operation).put("key", key);
        if (device != null) value.put("id", device);
        return value;
    }
    public static JSONObject open(SSLSocket socket, String host, int port, JSONObject request) throws Exception {
        socket.connect(new InetSocketAddress(host, port), 10000);
        SSLParameters parameters = socket.getSSLParameters(); parameters.setEndpointIdentificationAlgorithm("HTTPS");
        socket.setSSLParameters(parameters); socket.setSoTimeout(15000); socket.startHandshake();
        socket.getOutputStream().write((request.toString() + "\n").getBytes(StandardCharsets.UTF_8));
        socket.getOutputStream().flush();
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        InputStream input = socket.getInputStream();
        while (bytes.size() < 131072) {
            int next = input.read();
            if (next == -1) throw new EOFException("서버 연결 종료");
            if (next == '\n') {
                String line = new String(bytes.toByteArray(), StandardCharsets.UTF_8);
                if (!line.startsWith("{")) throw new IOException("중계서버를 최신 버전으로 업데이트하세요.");
                JSONObject response = new JSONObject(line);
                if (response.has("error")) {
                    String error = response.getString("error");
                    if (error.equals("unauthorized")) throw new IOException("서버 접속 키가 올바르지 않습니다.");
                    if (error.equals("offline")) throw new IOException("Target이 오프라인입니다.");
                    throw new IOException("Target에 연결할 수 없습니다. 목록을 새로고침하세요.");
                }
                return response;
            }
            bytes.write(next);
        }
        throw new IOException("서버 응답이 너무 큽니다.");
    }
}
