"use strict";
const params = new URLSearchParams(location.hash.slice(1));
const requestId = params.get("request"), masterToken = params.get("token");
history.replaceState(null, "", location.pathname);
// Another email link may open in this same tab without a document navigation.
window.addEventListener("hashchange", () => { if (location.hash) location.reload(); });
const byId = id => document.getElementById(id);
const labels = {pending: "사용자를 확인한 후 인증완료를 눌러 주세요.", approved: "인증이 완료되었습니다. 사용자가 새 회의를 시작할 수 있습니다.", rejected: "요청을 거절했습니다.", expired: "요청이 만료되었습니다. 사용자에게 다시 인증을 요청하도록 안내하세요.", used: "이 승인으로 이미 회의가 생성되었습니다.", failed: "이메일 발송에 실패한 요청입니다.", sending: "메일 발송을 마치는 중입니다. 이메일 링크를 잠시 후 다시 열어 주세요."};
async function call(path, body) {
  const response = await fetch(path, {method: body ? "POST" : "GET", cache: "no-store", headers: {Authorization: `Bearer ${masterToken}`, "Content-Type": "application/json"}, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(15000)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "요청을 처리하지 못했습니다.");
  return data;
}
async function load() {
  try {
    if (!requestId || !masterToken) throw new Error("Master에게 보낸 이메일의 승인 링크로 접속하세요.");
    const data = await call(`/api/master-approvals/${encodeURIComponent(requestId)}`);
    byId("request-details").hidden = false;
    byId("request-name").textContent = data.name;
    byId("request-contact").textContent = data.contact;
    byId("request-created").textContent = new Date(data.created_at * 1000).toLocaleString("ko-KR");
    byId("request-expires").textContent = new Date(data.expires_at * 1000).toLocaleString("ko-KR");
    byId("approval-result").textContent = labels[data.status] || "처리할 수 없는 요청입니다.";
    byId("decision-buttons").hidden = data.status !== "pending";
  } catch (e) { byId("approval-result").textContent = e.message; }
}
async function decide(decision) {
  byId("approve-host").disabled = byId("reject-host").disabled = true;
  try {
    const data = await call(`/api/master-approvals/${encodeURIComponent(requestId)}/decision`, {decision});
    byId("approval-result").textContent = labels[data.status];
    byId("decision-buttons").hidden = true;
  } catch (e) { byId("approval-result").textContent = e.message; }
  finally { byId("approve-host").disabled = byId("reject-host").disabled = false; }
}
byId("approve-host").onclick = () => decide("approve");
byId("reject-host").onclick = () => decide("reject");
load();
