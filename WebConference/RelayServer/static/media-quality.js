"use strict";
// Application thresholds, not an Internet speed test. Stats units: seconds and bits/s.
window.MoaQuality = (() => {
  const profiles = {
    low: { label: "360p", width: 640, height: 360, fps: 15, bitrate: 350000 },
    medium: { label: "540p", width: 960, height: 540, fps: 20, bitrate: 800000 },
    high: { label: "720p", width: 1280, height: 720, fps: 24, bitrate: 1500000 },
    full: { label: "1080p", width: 1920, height: 1080, fps: 30, bitrate: 2500000 },
  };
  const labels = ["측정 중", "매우 불안정", "불안정", "보통", "좋음", "매우 좋음"];
  const finite = v => typeof v === "number" && Number.isFinite(v) && v >= 0;
  function grade({ rtt = null, loss = null, jitter = null }) {
    const scores = [];
    for (const [value, limits] of [[rtt, [150, 300, 500, 800]], [loss, [1, 3, 5, 10]], [jitter, [20, 40, 80, 150]]]) {
      if (finite(value)) { const i = limits.findIndex(limit => value < limit); scores.push(i < 0 ? 1 : 5 - i); }
    }
    return scores.length ? Math.min(...scores) : 0;
  }
  class Sampler {
    constructor() { this.history = new WeakMap(); }
    async read(pc) {
      if (["failed", "closed", "disconnected"].includes(pc.connectionState))
        return { level: pc.connectionState === "disconnected" ? 2 : 1, disconnected: true };
      if (pc.connectionState !== "connected") return { level: 0 };
      const stats = await pc.getStats(), now = performance.now();
      const previous = this.history.get(pc) || new Map(), next = new Map();
      const values = { rtt: [], loss: [], jitter: [] };
      let outgoing = null, cpuLimited = false;
      const selected = new Set();
      stats.forEach(s => { if (s.type === "transport" && s.selectedCandidatePairId) selected.add(s.selectedCandidatePairId); });
      stats.forEach(s => {
        if (s.type === "candidate-pair" && s.state === "succeeded" && (selected.has(s.id) || (!selected.size && s.nominated))) {
          if (finite(s.currentRoundTripTime)) values.rtt.push(s.currentRoundTripTime * 1000);
          if (finite(s.availableOutgoingBitrate)) outgoing = s.availableOutgoingBitrate;
        }
        if (s.type === "outbound-rtp" && s.kind === "video" && s.qualityLimitationReason === "cpu") cpuLimited = true;
        if (!["inbound-rtp", "remote-inbound-rtp"].includes(s.type)) return;
        const old = previous.get(s.id);
        // Remote RTCP reports may keep the same timestamp across several polls.
        const changed = s.type === "remote-inbound-rtp" ? !old || s.timestamp !== old.timestamp
          : !old || s.packetsReceived !== old.packetsReceived || s.packetsLost !== old.packetsLost;
        const freshAt = changed ? now : old.freshAt;
        next.set(s.id, { ...s, freshAt });
        if (now - freshAt > 12000) return;
        if (finite(s.jitter)) values.jitter.push(s.jitter * 1000);
        if (finite(s.roundTripTime)) values.rtt.push(s.roundTripTime * 1000);
        if (s.type === "remote-inbound-rtp") {
          if (finite(s.fractionLost)) values.loss.push(Math.min(100, s.fractionLost * 100));
        } else if (old && finite(s.packetsReceived) && finite(s.packetsLost)) {
          const received = s.packetsReceived - old.packetsReceived, lost = s.packetsLost - old.packetsLost;
          if (received >= 0 && lost >= 0 && received + lost > 0) values.loss.push(lost / (received + lost) * 100);
        }
      });
      this.history.set(pc, next);
      const result = Object.fromEntries(Object.entries(values).map(([k, a]) => [k, a.length ? Math.max(...a) : null]));
      return { ...result, level: grade(result), outgoing, cpuLimited };
    }
  }
  class AutoProfile {
    constructor() { this.current = "medium"; this.candidate = null; this.hits = 0; }
    update(sample) {
      if (!sample?.level) { this.hits = 0; this.candidate = null; return this.current; }
      let desired = sample.level <= 2 ? "low" : sample.level === 3 ? "medium" : "high";
      if (finite(sample.outgoing)) {
        if (sample.outgoing < 600000) desired = "low";
        else if (sample.outgoing < 1800000 && desired === "high") desired = "medium";
      }
      if (sample.cpuLimited) desired = "low";
      if (desired === this.current) { this.hits = 0; this.candidate = null; return this.current; }
      this.hits = this.candidate === desired ? this.hits + 1 : 1; this.candidate = desired;
      const worsening = profiles[desired].height < profiles[this.current].height;
      if (this.hits >= (worsening ? 2 : 5)) { this.current = desired; this.hits = 0; this.candidate = null; }
      return this.current;
    }
  }
  function constraints(key) {
    const p = profiles[key];
    return { width: { ideal: p.width }, height: { ideal: p.height }, frameRate: { ideal: p.fps, max: p.fps } };
  }
  return { profiles, labels, grade, Sampler, AutoProfile, constraints };
})();
