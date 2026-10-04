package com.remotecontrol;

/** Monotonic timestamps; owned by the Host UI thread. */
public final class ConnectionHealth {
    public static final long PING_INTERVAL_MS = 1000, SLOW_RTT_MS = 700;
    public static final long DELAY_MS = 2500, LOST_MS = 5000, TIMEOUT_MS = 10000;
    public enum State { IDLE, CONNECTING, CHECKING, GOOD, VIEW_ONLY, CONTROL_UNAVAILABLE, DELAYED, UNRESPONSIVE, DISCONNECTED }
    private State inactive = State.IDLE;
    private boolean active, receivedReply, receivedFrame, allowed, ready;
    private long lastReply, lastSent = -1, pending = -1, rtt = -1;
    private final long[] samples = new long[10];
    private int sampleCount, nextSample;

    public void connecting() { reset(); inactive = State.CONNECTING; }
    public void connected(long now) { reset(); active = true; lastReply = now; }
    public void disconnected(boolean error) { reset(); inactive = error ? State.DISCONNECTED : State.IDLE; }
    private void reset() {
        active = receivedReply = receivedFrame = allowed = ready = false;
        lastSent = pending = rtt = -1;
        sampleCount = nextSample = 0;
    }
    public boolean needsPing(long now) { return active && pending == -1 && (lastSent == -1 || now - lastSent >= PING_INTERVAL_MS); }
    public void sent(long now) { pending = lastSent = now; }
    public boolean pong(long echo, long now, boolean controlAllowed, boolean controlReady) {
        if (!active || pending == -1 || echo != pending || now < echo) return false;
        rtt = now - pending; pending = -1; lastReply = now; receivedReply = true;
        samples[nextSample] = rtt; nextSample = (nextSample + 1) % samples.length;
        sampleCount = Math.min(samples.length, sampleCount + 1);
        allowed = controlAllowed; ready = controlReady; return true;
    }
    public void frame() { if (active) receivedFrame = true; }
    public long rtt() { return rtt; }
    public int sampleCount() { return sampleCount; }
    public long silence(long now) { return active ? Math.max(0, now - lastReply) : 0; }
    public long jitter() {
        if (sampleCount < 2) return 0;
        long sum = 0;
        int first = (nextSample - sampleCount + samples.length) % samples.length;
        for (int i = 1; i < sampleCount; i++)
            sum += Math.abs(samples[(first + i) % samples.length] - samples[(first + i - 1) % samples.length]);
        return sum / (sampleCount - 1);
    }
    public int latePercent() {
        if (sampleCount == 0) return 0;
        int count = 0;
        for (int i = 0; i < sampleCount; i++) if (samples[i] >= SLOW_RTT_MS) count++;
        return count * 100 / sampleCount;
    }
    /** 0..9: combine current response time, recent instability and unanswered probes. */
    public int qualityLevel(long now) {
        if (!active) return inactive == State.DISCONNECTED ? 9 : -1;
        if (!receivedReply) return silence(now) >= LOST_MS ? (silence(now) >= 8000 ? 9 : 8) : -1;
        long latency = Math.max(rtt, pending == -1 ? 0 : Math.max(0, now - pending));
        int level = latency < 100 ? 0 : latency < 200 ? 1 : latency < 350 ? 2 : latency < 500 ? 3
                : latency < 700 ? 4 : latency < 1000 ? 5 : latency < 1500 ? 6 : 7;
        if (sampleCount >= 3) {
            long variation = jitter();
            level = Math.max(level, variation >= 500 ? 7 : variation >= 300 ? 6 : variation >= 150 ? 4 : variation >= 75 ? 2 : 0);
        }
        if (sampleCount >= 4) {
            int late = latePercent();
            level = Math.max(level, late >= 50 ? 6 : late >= 30 ? 5 : late >= 10 ? 3 : 0);
        }
        long silence = silence(now);
        return Math.max(level, silence >= 8000 ? 9 : silence >= LOST_MS ? 8 : silence >= 3500 ? 7 : silence >= DELAY_MS ? 5 : 0);
    }
    public boolean timedOut(long now) { return active && now - lastReply >= TIMEOUT_MS; }
    public boolean canSendControl(long now) { return active && receivedReply && receivedFrame && allowed && ready && now - lastReply < LOST_MS; }
    public State state(long now) {
        if (!active) return inactive;
        long silence = now - lastReply;
        if (silence >= LOST_MS) return State.UNRESPONSIVE;
        if (silence >= DELAY_MS || rtt >= SLOW_RTT_MS) return State.DELAYED;
        if (!receivedReply || !receivedFrame) return State.CHECKING;
        if (!allowed) return State.VIEW_ONLY;
        return ready ? State.GOOD : State.CONTROL_UNAVAILABLE;
    }
}
