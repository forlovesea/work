package com.batterywatch.monitor;

import java.net.URI;

public final class Endpoint {
    private Endpoint() {}
    public static String validate(String value, boolean debug) {
        URI uri;
        try { uri = URI.create(value.trim()); }
        catch (RuntimeException e) { throw new IllegalArgumentException("서버 주소를 확인하세요."); }
        String host = uri.getHost();
        boolean local = "127.0.0.1".equals(host) || "localhost".equals(host) || "10.0.2.2".equals(host);
        if (host == null || uri.getUserInfo() != null || uri.getRawQuery() != null || uri.getFragment() != null
                || (uri.getPath() != null && !uri.getPath().isEmpty() && !"/".equals(uri.getPath()))
                || uri.getPort() == 0 || uri.getPort() > 65535
                || !("https".equals(uri.getScheme()) || (debug && local && "http".equals(uri.getScheme())))) {
            throw new IllegalArgumentException("https://서버주소:8443 형식으로 입력하세요. HTTP는 디버그 로컬 시험만 가능합니다.");
        }
        return value.trim().replaceAll("/+$", "");
    }
}
