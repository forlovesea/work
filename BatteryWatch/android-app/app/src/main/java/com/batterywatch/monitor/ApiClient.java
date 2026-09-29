package com.batterywatch.monitor;

import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

final class ApiClient {
    final String base, token;
    ApiClient(String base, String token) { this.base = Endpoint.validate(base, BuildConfig.DEBUG); this.token = token; }
    static String query(String site, String device) {
        return "?site_id=" + encode(site) + "&device_id=" + encode(device);
    }
    private static String encode(String value) {
        try { return URLEncoder.encode(value, "UTF-8"); } catch (Exception e) { throw new IllegalArgumentException(e); }
    }
    JSONObject get(String path) throws Exception { return request("GET", path, null); }
    JSONObject request(String method, String path, JSONObject body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(base + path).openConnection();
        try {
            c.setConnectTimeout(5000); c.setReadTimeout(10000); c.setInstanceFollowRedirects(false);
            c.setRequestProperty("Authorization", "Bearer " + token); c.setRequestProperty("Accept", "application/json");
            c.setRequestMethod(method);
            if (body != null) {
                byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
                c.setDoOutput(true); c.setFixedLengthStreamingMode(bytes.length);
                c.setRequestProperty("Content-Type", "application/json");
                try (java.io.OutputStream out = c.getOutputStream()) { out.write(bytes); }
            }
            int code = c.getResponseCode();
            if (code != 200) {
                String message = switch (code) {
                    case 401 -> "인증 토큰이 올바르지 않습니다.";
                    case 403 -> "이 장비의 조회 권한이 없습니다.";
                    case 404 -> "저장된 데이터가 아직 없거나 API 주소가 다릅니다.";
                    default -> "서버 응답 오류 (" + code + ")";
                };
                throw new IOException(message);
            }
            try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192]; int n;
                while ((n = in.read(buffer)) != -1) {
                    if (out.size() + n > 20 * 1024 * 1024) throw new IOException("서버 응답이 너무 큽니다.");
                    out.write(buffer, 0, n);
                }
                return new JSONObject(out.toString("UTF-8"));
            }
        } finally { c.disconnect(); }
    }
}
