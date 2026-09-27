"use strict";

let socket;
let domains = new Set();
let reconnectTimer;
const recent = new Map();

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
  const current = new WebSocket("ws://127.0.0.1:47832/browser");
  socket = current;
  current.onmessage = event => {
    if (socket !== current) return;
    try {
      const policy = JSON.parse(event.data);
      if (policy.type === "domains" && Array.isArray(policy.domains)) {
        domains = new Set(policy.domains.filter(x => typeof x === "string").map(x => x.toLowerCase()));
      }
    } catch { /* Ignore invalid policy data. */ }
  };
  current.onerror = () => current.close();
  current.onclose = () => {
    if (socket !== current) return;
    socket = undefined;
    domains.clear();
    recent.clear();
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 3000);
  };
}

function visit(details) {
  if (details.frameId !== 0 || !socket || socket.readyState !== WebSocket.OPEN) return;
  let url;
  try { url = new URL(details.url); } catch { return; }
  if (url.protocol !== "http:" && url.protocol !== "https:") return;
  const host = url.hostname.toLowerCase().replace(/\.$/, "");
  if (!domains.has(host) && !(host.startsWith("www.") && domains.has(host.slice(4)))) return;
  const now = performance.now();
  const previous = recent.get(host);
  if (previous !== undefined && now - previous < 1000) return;
  for (const [key, time] of recent) if (now - time >= 1000) recent.delete(key);
  recent.set(host, now);
  // Only the origin is sent, never paths, search terms, page content or passwords.
  socket.send(JSON.stringify({ url: url.origin }));
}

chrome.webNavigation.onBeforeNavigate.addListener(visit);
chrome.webNavigation.onErrorOccurred.addListener(visit);
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === "safechild-connect") connect(); });
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
chrome.alarms.create("safechild-connect", { periodInMinutes: 1 });
connect();
