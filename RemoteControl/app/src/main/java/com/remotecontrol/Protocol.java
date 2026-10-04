package com.remotecontrol;

public final class Protocol {
    public static final int MIN_RELAY_PORT = 55000, MAX_RELAY_PORT = 60000;
    public static final int DEFAULT_RELAY_PORT = 55000;
    public static final int MAX_FRAME = 2 * 1024 * 1024;
    public static final int GESTURE = 1, BACK = 2, HOME = 3, PING = 4;
    public static final int PONG = -1;
    public static final String WIRE_VERSION = "2";
    private Protocol() {}
    public static boolean relayPort(int port) {
        return port >= MIN_RELAY_PORT && port <= MAX_RELAY_PORT;
    }
    public static boolean coordinate(float value) {
        return Float.isFinite(value) && value >= 0 && value <= 1;
    }
    public static String[] invitation(String value) {
        String[] parts = value.trim().split("\\|", -1);
        if (parts.length != 7 || !parts[0].equals("RC2") || !parts[1].matches("[a-zA-Z0-9.-]{1,253}")
                || !parts[2].matches("[0-9]{1,5}") || !relayPort(Integer.parseInt(parts[2]))
                || !parts[3].matches("[0-9a-f]{32}") || !parts[4].matches("[0-9a-fA-F]{64}")
                || !parts[5].matches("[0-9a-f]{32}") || !parts[6].equals(WIRE_VERSION)) {
            throw new IllegalArgumentException("두 앱을 최신 버전으로 설치하고 Target의 새 접속 정보를 붙여 넣으세요.");
        }
        return parts;
    }
}
