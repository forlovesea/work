"use strict";
const $ = (id) => document.getElementById(id);
const state = {
  create: false, ws: null, session: null, room: null, config: null,
  mic: false, speaker: false, camera: false, publisher: null, local: null,
  audioContext: null, micTrack: null, cameraTrack: null, shareTrack: null,
  silentTrack: null, blankTrack: null, canvasTimer: null,
  peers: new Map(), streams: new Map(), pending: new Map(), requestId: 0,
  entries: [], strokes: [], view: "grid", busy: false, leaving: false, speechPending: 0,
};
let toastTimer;
function toast(message) {
  $("toast").textContent = message; $("toast").hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $("toast").hidden = true, 6500);
}
function safeAction(fn) { return async (...args) => { try { await fn(...args); } catch (e) { toast(e.message || "요청을 처리하지 못했습니다."); } }; }
function serverURL() {
  const url = new URL($("server").value.trim());
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || (url.pathname !== "/")) throw new Error("서버 주소는 http(s)://호스트:포트 형식으로 입력하세요.");
  if (location.protocol === "https:" && url.protocol !== "https:") throw new Error("HTTPS 화면에서는 HTTPS 서버 주소를 사용하세요.");
  return url.origin;
}
async function api(path, data, token) {
  const headers = {}; if (data) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(serverURL() + path, { method: data ? "POST" : "GET", headers, body: data ? JSON.stringify(data) : undefined, signal: AbortSignal.timeout(15000) });
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(typeof err.detail === "string" ? err.detail : `요청 실패 (${res.status})`); }
  return res;
}
async function checkServer() {
  $("server-state").textContent = "서버에 연결하는 중…";
  try {
    state.config = await (await api("/api/config")).json();
    $("server-state").textContent = `연결됨 · 한 방 최대 ${state.config.max_participants}명`;
    $("speech-hint").textContent = state.config.speech_available ? (state.config.speech_engine === "faster-whisper" ? "한국어 정밀 전사 준비 완료 · 발화 후 순서대로 기록되며 표시가 늦을 수 있습니다." : "한국어 음성 인식 준비 완료 · 모든 참석자에게 기록 상태가 표시됩니다.") : state.config.speech_message;
    updateMinutesOption();
  } catch (e) {
    state.config = null; updateMinutesOption();
    $("server-state").textContent = "연결 실패 · 주소, HTTPS, 서버의 접속 허용 설정을 확인하세요.";
    throw e;
  }
}
function updateMinutesOption() {
  $("pref-minutes").disabled = !state.config?.speech_available || $("mode").value !== "meeting";
  if ($("pref-minutes").disabled) $("pref-minutes").checked = false;
}
function setCreate(value) {
  state.create = value; $("create-fields").hidden = !value; $("join-fields").hidden = value;
  $("create-tab").classList.toggle("active", value); $("join-tab").classList.toggle("active", !value);
  $("create-tab").setAttribute("aria-selected", String(value)); $("join-tab").setAttribute("aria-selected", String(!value));
  $("enter").firstChild.textContent = value ? "새 회의 시작하기 " : "회의 참여하기 ";
  $("code").required = !value; $("title").required = value;
}
function invitationURL() {
  const url = new URL("/", serverURL());
  // Share only the room's invitation code, never the participant/host token.
  url.hash = new URLSearchParams({ room: state.session.code }).toString();
  return url.href;
}
function renderInvitation() {
  $("host-invite").hidden = !isHost();
  if (!isHost()) { $("invite-link").value = ""; return; }
  const url = invitationURL();
  if ($("invite-link").value !== url) $("invite-link").value = url;
  const hostname = new URL(url).hostname;
  $("invite-help").textContent = ["localhost", "127.0.0.1", "[::1]"].includes(hostname)
    ? "현재는 이 PC 전용 주소입니다. 다른 PC를 초대하려면 접속 가능한 HTTPS 서버에서 방을 만들어 주세요."
    : "링크를 받은 사람은 이름을 입력하고 참여할 수 있어요. 방이 종료되면 링크도 만료됩니다.";
}
async function copyInvitation() {
  if (!isHost()) throw new Error("방장만 초대 링크 메뉴를 사용할 수 있습니다.");
  try {
    await navigator.clipboard.writeText(invitationURL());
    toast("초대 링크를 복사했습니다. 메신저나 이메일에 붙여 넣어 공유하세요.");
  } catch (_) {
    $("invite-link").focus(); $("invite-link").select();
    toast("자동 복사가 허용되지 않았습니다. 선택된 링크를 Ctrl+C 또는 길게 눌러 복사하세요.");
  }
}
function loadInvitation() {
  const params = new URLSearchParams(location.hash.slice(1));
  if (!params.has("room")) return;
  // An invitation belongs to the site being opened, regardless of saved settings.
  $("server").value = location.origin;
  const code = params.get("room").replace(/[\s-]/g, "").toUpperCase();
  $("invite-notice").hidden = false;
  if (!/^[A-F0-9]{12}$/.test(code)) {
    $("code").value = "";
    $("invite-notice").textContent = "초대 링크의 접속 ID가 올바르지 않습니다. 방장에게 링크를 다시 받거나 접속 ID를 직접 입력해 주세요.";
    return;
  }
  $("code").value = code;
  $("invite-notice").textContent = "초대 링크로 접속했습니다. 서버 주소와 방 접속 ID가 입력되어 있어요. 이름과 장치 설정을 확인하고 회의 참여하기를 누르세요.";
}
function rpc(action, data = {}) {
  return new Promise((resolve, reject) => {
    if (state.ws?.readyState !== WebSocket.OPEN) return reject(new Error("서버 연결이 끊어졌습니다."));
    const id = ++state.requestId;
    const timer = setTimeout(() => { state.pending.delete(id); reject(new Error("서버 응답이 지연됩니다. 네트워크를 확인하세요.")); }, 60000);
    state.pending.set(id, { resolve, reject, timer });
    state.ws.send(JSON.stringify({ id, action, ...data }));
  });
}
async function connectSocket() {
  const url = new URL(serverURL() + "/ws"); url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url); state.ws = ws;
    const timer = setTimeout(() => { ws.close(); reject(new Error("서버 연결 시간이 초과되었습니다.")); }, 12000);
    ws.onopen = () => ws.send(JSON.stringify({ token: state.session.token }));
    ws.onerror = () => { clearTimeout(timer); reject(new Error("중계 서버와 연결하지 못했습니다.")); };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "reply") {
        const request = state.pending.get(data.id);
        if (request) { clearTimeout(request.timer); state.pending.delete(data.id); data.ok ? request.resolve(data.result) : request.reject(new Error(data.error)); }
      } else if (data.type === "welcome") {
        clearTimeout(timer); state.entries = data.entries; state.strokes = data.strokes;
        updateSpeechStatus(data.speech_pending || 0);
        updateRoom(data.room); renderEntries(); redrawBoard(); resolve();
      } else if (data.type === "state") updateRoom(data.room);
      else if (data.type === "entry") { state.entries.push(data.entry); state.entries = state.entries.slice(-200); renderEntries(); }
      else if (data.type === "stroke") { state.strokes.push(data.stroke); if (data.author !== state.session?.participant_id) drawStroke(data.stroke); }
      else if (data.type === "board") { state.strokes = data.strokes; redrawBoard(); }
      else if (data.type === "speech_status") updateSpeechStatus(data.pending);
      else if (data.type === "notice") toast(data.message);
    };
    ws.onclose = () => {
      clearTimeout(timer); reject(new Error("서버 연결이 종료되었습니다."));
      for (const req of state.pending.values()) { clearTimeout(req.timer); req.reject(new Error("서버 연결이 종료되었습니다.")); }
      state.pending.clear();
      if (!state.leaving && state.session) { toast("연결이 끊어졌습니다. 접속 ID로 다시 입장해 주세요."); leave(); }
    };
  });
}
async function prepareMedia() {
  if (!window.isSecureContext || !navigator.mediaDevices) throw new Error("카메라·마이크 사용을 위해 HTTPS 또는 localhost로 접속하세요.");
  const context = new AudioContext(); state.audioContext = context;
  const destination = context.createMediaStreamDestination();
  const oscillator = context.createOscillator(), gain = context.createGain(); gain.gain.value = 0;
  oscillator.connect(gain).connect(destination); oscillator.start();
  state.silentTrack = destination.stream.getAudioTracks()[0];
  await context.resume();
  const canvas = document.createElement("canvas"); canvas.width = 640; canvas.height = 360;
  const draw = () => { const ctx = canvas.getContext("2d"); ctx.fillStyle = "#e2e8ef"; ctx.fillRect(0, 0, 640, 360); };
  draw(); state.canvasTimer = setInterval(draw, 200); state.blankTrack = canvas.captureStream(5).getVideoTracks()[0];
  if (state.mic) state.micTrack = (await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })).getAudioTracks()[0];
  if (state.camera) state.cameraTrack = (await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 960 }, height: { ideal: 540 }, frameRate: { ideal: 20, max: 24 } } })).getVideoTracks()[0];
  state.local = new MediaStream([state.micTrack || state.silentTrack, state.cameraTrack || state.blankTrack]);
}
async function iceComplete(pc) {
  if (pc.iceGatheringState === "complete") return;
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pc.removeEventListener("icegatheringstatechange", change); reject(new Error("미디어 경로를 찾지 못했습니다. STUN/TURN 설정을 확인하세요.")); }, 20000);
    function change() { if (pc.iceGatheringState === "complete") { clearTimeout(timer); pc.removeEventListener("icegatheringstatechange", change); resolve(); } }
    pc.addEventListener("icegatheringstatechange", change);
  });
}
async function negotiate(pc, action, extra = {}) {
  await pc.setLocalDescription(await pc.createOffer()); await iceComplete(pc);
  const answer = await rpc(action, { sdp: pc.localDescription.sdp, ...extra });
  await pc.setRemoteDescription(answer);
}
async function publish() {
  const pc = new RTCPeerConnection({ iceServers: state.session.ice_servers }); state.publisher = pc;
  for (const track of state.local.getTracks()) pc.addTrack(track, state.local);
  pc.onconnectionstatechange = () => { if (pc.connectionState === "failed") toast("미디어 연결 실패 · 서버의 UDP 방화벽과 TURN 설정을 확인한 후 다시 입장하세요."); };
  await negotiate(pc, "publish");
}
async function subscribe(person) {
  if (state.peers.has(person.id) || person.id === state.session?.participant_id || !person.ready) return;
  const pc = new RTCPeerConnection({ iceServers: state.session.ice_servers });
  state.peers.set(person.id, pc);
  pc.addTransceiver("audio", { direction: "recvonly" }); pc.addTransceiver("video", { direction: "recvonly" });
  const stream = new MediaStream(); state.streams.set(person.id, stream);
  pc.ontrack = (event) => {
    stream.addTrack(event.track);
    if (event.track.kind === "audio") {
      let audio = document.getElementById(`audio-${person.id}`);
      if (!audio) { audio = document.createElement("audio"); audio.id = `audio-${person.id}`; audio.autoplay = true; $("remote-audio").append(audio); }
      audio.srcObject = new MediaStream([event.track]); audio.muted = !state.speaker;
      audio.play().catch(() => { if (state.speaker) toast("소리 재생을 허용하려면 스피커 버튼을 다시 눌러주세요."); });
    }
    renderTiles(); renderFocus();
  };
  pc.onconnectionstatechange = () => { if (pc.connectionState === "failed") toast(`${person.name} 님의 영상 연결에 실패했습니다. 다시 입장해 주세요.`); };
  try { await negotiate(pc, "subscribe", { target: person.id }); }
  catch (e) { pc.close(); state.peers.delete(person.id); if (state.room?.participants.some(p => p.id === person.id) && !state.leaving) toast(e.message); }
}
async function enter(event) {
  event.preventDefault(); if (state.busy) return;
  state.busy = true; state.leaving = false; $("enter").disabled = true;
  try {
    await checkServer();
    state.mic = $("pref-mic").checked; state.speaker = $("pref-speaker").checked; state.camera = $("pref-camera").checked;
    // Only name and address persist. Device use always starts with an explicit choice.
    try { localStorage.setItem("moa-settings", JSON.stringify({ server: serverURL(), name: $("name").value.trim() })); } catch (_) { /* Private mode */ }
    await prepareMedia();
    state.session = await (await api(state.create ? "/api/rooms" : "/api/join", state.create ? {
      title: $("title").value.trim(), name: $("name").value.trim(), mode: $("mode").value, minutes_enabled: $("pref-minutes").checked,
    } : { code: $("code").value.trim(), name: $("name").value.trim() })).json();
    $("code").value = state.session.code;
    await connectSocket();
    $("lobby").hidden = true; $("conference").hidden = false; $("footer").hidden = true;
    await rpc("devices", { mic: state.mic, camera: state.camera });
    await publish(); renderTiles();
    toast("입장했습니다. 마이크와 스피커 상태를 확인해 주세요.");
  } catch (e) { await leave(); toast(e.message || "회의에 입장하지 못했습니다."); }
  finally { state.busy = false; $("enter").disabled = false; }
}
function me() { return state.room?.participants.find(p => p.id === state.session?.participant_id); }
function isHost() { return state.room?.host_id === state.session?.participant_id; }
function isPresenter() { return state.room?.presenter_id === state.session?.participant_id; }
function updateRoom(room) {
  const previousPresenter = state.room?.presenter_id;
  state.room = room;
  $("room-title").textContent = room.title; $("mode-badge").textContent = room.mode === "free" ? "FREE TALK" : "회의 모드";
  $("room-code").textContent = room.code.match(/.{1,4}/g).join("-");
  renderInvitation();
  $("connection-label").textContent = `${room.participants.length}명이 함께하는 중`;
  if (state.micTrack) state.micTrack.enabled = !!me()?.can_speak;
  if (state.shareTrack && !isPresenter()) safeAction(() => stopShare(false))();
  $("floor-label").textContent = room.mode === "free" ? "자유롭게 대화하는 시간입니다. 마이크를 켜고 함께 이야기하세요." :
    isPresenter() ? "지금은 나의 발표 시간입니다. 마이크를 켜고 이야기하세요." : `${room.participants.find(p => p.id === room.presenter_id)?.name || "다음 발표자"} 님의 발표 시간 · 손을 들어 발언을 요청하세요.`;
  $("hand").textContent = room.hands.includes(state.session?.participant_id) ? "손 내리기" : "손들기";
  $("share").disabled = !isPresenter(); $("clear-board").disabled = !isPresenter();
  $("board-hint").textContent = isPresenter() ? "내가 발표자입니다. 마우스나 손가락으로 그려보세요." : "발표자가 그린 내용이 모두에게 표시됩니다.";
  $("note-form").hidden = !isHost(); $("toggle-minutes").hidden = !isHost() || room.mode !== "meeting";
  $("toggle-minutes").disabled = !state.config?.speech_available;
  $("toggle-minutes").textContent = room.minutes_enabled ? "끄기" : "켜기";
  $("record-label").textContent = room.minutes_enabled ? "● 음성 인식 기록 중" : "자동 기록 꺼짐";
  $("record-label").parentElement.classList.toggle("recording", room.minutes_enabled);
  for (const [pid, pc] of state.peers) if (!room.participants.some(p => p.id === pid)) { pc.close(); state.peers.delete(pid); state.streams.delete(pid); document.getElementById(`audio-${pid}`)?.remove(); }
  renderPeople(); renderTiles(); renderFocus(); updateControls();
  for (const person of room.participants) subscribe(person);
  if (previousPresenter && previousPresenter !== room.presenter_id) redrawBoard();
}
function renderPeople() {
  $("people-count").textContent = state.room.participants.length; $("people").replaceChildren();
  for (const person of state.room.participants) {
    const row = document.createElement("div"); row.className = "person";
    const avatar = document.createElement("span"); avatar.className = "person-avatar"; avatar.textContent = person.name.slice(0, 1);
    const info = document.createElement("div"); info.className = "person-info";
    const name = document.createElement("b"); name.textContent = person.name + (person.id === state.session.participant_id ? " (나)" : "");
    const detail = document.createElement("small");
    detail.textContent = [person.id === state.room.host_id ? "방장" : "참석자", person.id === state.room.presenter_id ? "발표자" : "", state.room.hands.includes(person.id) ? "✋ 발언 요청" : "", person.can_speak ? "마이크 켜짐" : "음성 꺼짐"].filter(Boolean).join(" · ");
    info.append(name, detail); row.append(avatar, info);
    if (isHost() && person.id !== state.room.presenter_id) { const button = document.createElement("button"); button.textContent = "발표 지정"; button.onclick = safeAction(() => rpc("presenter", { target: person.id })); row.append(button); }
    $("people").append(row);
  }
}
function streamFor(pid) { return pid === state.session?.participant_id ? state.local : state.streams.get(pid); }
function renderTiles() {
  if (!state.room) return;
  const ids = new Set(state.room.participants.map(p => p.id));
  for (const tile of [...$("grid").children]) if (!ids.has(tile.dataset.pid)) tile.remove();
  for (const person of state.room.participants) {
    let tile = document.getElementById(`tile-${person.id}`);
    if (!tile) {
      tile = document.createElement("div"); tile.id = `tile-${person.id}`; tile.dataset.pid = person.id; tile.className = "tile";
      const video = document.createElement("video"); video.autoplay = true; video.muted = true; video.playsInline = true;
      const avatar = document.createElement("div"); avatar.className = "avatar";
      const label = document.createElement("div"); label.className = "tile-label";
      const status = document.createElement("div"); status.className = "tile-status";
      tile.append(video, avatar, label, status); $("grid").append(tile);
    }
    const video = tile.querySelector("video"), stream = streamFor(person.id);
    if (stream && video.srcObject !== stream) video.srcObject = stream;
    const visible = (person.camera || person.sharing) && !!stream?.getVideoTracks().length;
    video.hidden = !visible; tile.querySelector(".avatar").hidden = visible; tile.querySelector(".avatar").textContent = person.name.slice(0, 1);
    tile.querySelector(".tile-label").textContent = person.name + (person.id === state.session.participant_id ? " (나)" : "");
    tile.querySelector(".tile-status").textContent = person.can_speak ? "음성 켜짐" : "음성 꺼짐";
    tile.classList.toggle("speaking", person.can_speak); tile.classList.toggle("sharing", person.sharing);
  }
}
function renderFocus() {
  if (!state.room) return;
  const person = state.room.participants.find(p => p.id === state.room.presenter_id), stream = person ? streamFor(person.id) : null;
  if ($("focus-video").srcObject !== (stream || null)) $("focus-video").srcObject = stream || null;
  if (stream && state.view === "focus") $("focus-video").play().catch(() => {});
  const visible = person && (person.camera || person.sharing) && stream?.getVideoTracks().length;
  $("focus-placeholder").hidden = !!visible;
  $("focus-placeholder").textContent = person ? `${person.name} 님의 카메라가 꺼져 있습니다.` : "발표자를 기다리고 있습니다.";
  $("focus-name").textContent = person ? `${person.name}${person.sharing ? " · 화면 공유 중" : " · 발표자"}` : "";
}
function setView(view) {
  state.view = view; $("grid").hidden = view !== "grid"; $("focus").hidden = view !== "focus"; $("board-view").hidden = view !== "board";
  document.querySelectorAll("[data-view]").forEach(button => { button.classList.toggle("active", button.dataset.view === view); button.setAttribute("aria-selected", String(button.dataset.view === view)); });
  if (view === "board") redrawBoard(); if (view === "focus") renderFocus();
}
function updateControls() {
  for (const [id, value, label] of [["toggle-mic", state.mic, "마이크"], ["toggle-speaker", state.speaker, "스피커"], ["toggle-camera", state.camera, "카메라"]]) {
    $(id).classList.toggle("on", value); $(id).setAttribute("aria-pressed", String(value));
    $(id).querySelector("b").textContent = `${label} ${value ? "켜짐" : "꺼짐"}`;
  }
  if (state.mic && !me()?.can_speak) $("toggle-mic").querySelector("b").textContent = "마이크 대기";
  $("share").classList.toggle("on", !!state.shareTrack); $("share").querySelector("b").textContent = state.shareTrack ? "공유 중지" : "화면·파일 공유";
}
async function replaceTrack(kind, track) {
  const sender = state.publisher?.getSenders().find(s => s.track?.kind === kind);
  if (sender) await sender.replaceTrack(track);
  const old = state.local?.getTracks().find(t => t.kind === kind);
  if (old) state.local.removeTrack(old); state.local?.addTrack(track);
}
async function toggleMic() {
  const enabled = !state.mic;
  if (enabled) {
    state.micTrack = (await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })).getAudioTracks()[0];
    state.micTrack.enabled = state.room.mode === "free" || isPresenter();
    await replaceTrack("audio", state.micTrack);
  } else { await replaceTrack("audio", state.silentTrack); state.micTrack?.stop(); state.micTrack = null; }
  state.mic = enabled; await rpc("devices", { mic: enabled }); updateControls();
}
async function toggleCamera() {
  const enabled = !state.camera;
  if (enabled) state.cameraTrack = (await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 960 }, height: { ideal: 540 }, frameRate: { ideal: 20, max: 24 } } })).getVideoTracks()[0];
  if (!state.shareTrack) await replaceTrack("video", enabled ? state.cameraTrack : state.blankTrack);
  if (!enabled) { state.cameraTrack?.stop(); state.cameraTrack = null; }
  state.camera = enabled; await rpc("devices", { camera: enabled }); renderTiles(); renderFocus(); updateControls();
}
async function toggleSpeaker() {
  state.speaker = !state.speaker;
  await state.audioContext?.resume();
  for (const audio of $("remote-audio").children) { audio.muted = !state.speaker; if (state.speaker) await audio.play(); }
  updateControls();
}
async function share() {
  if (state.shareTrack) return stopShare();
  if (!isPresenter()) throw new Error("발표자만 화면을 공유할 수 있습니다.");
  if (!navigator.mediaDevices.getDisplayMedia) throw new Error("이 브라우저는 화면 공유를 지원하지 않습니다. 데스크톱 Chrome 또는 Edge를 사용하세요.");
  const stream = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 15 }, audio: false });
  const track = stream.getVideoTracks()[0];
  try {
    await rpc("sharing", { enabled: true }); state.shareTrack = track;
    await replaceTrack("video", track); track.onended = safeAction(() => stopShare());
    setView("focus"); renderTiles(); renderFocus(); updateControls();
  } catch (e) { track.stop(); throw e; }
}
async function stopShare(notify = true) {
  const track = state.shareTrack; state.shareTrack = null;
  if (track) { track.onended = null; track.stop(); }
  if (state.local && state.blankTrack) await replaceTrack("video", state.cameraTrack || state.blankTrack);
  if (notify && state.ws?.readyState === WebSocket.OPEN) await rpc("sharing", { enabled: false });
  renderTiles(); renderFocus(); updateControls();
}
function updateSpeechStatus(pending) {
  state.speechPending = pending;
  $("speech-pending").textContent = state.config?.speech_engine === "faster-whisper"
    ? `음성 수집·인식 대기 ${pending}건 · 저장 전 자동 기록을 끄고 0건이 될 때까지 기다려 주세요.` : "";
}
function renderEntries() {
  const list = $("entries"); list.replaceChildren();
  if (!state.entries.length) { const p = document.createElement("p"); p.className = "empty-note"; p.textContent = "아직 기록된 내용이 없습니다."; list.append(p); }
  const kinds = { speech: "음성 전사", note: "추가 메모", decision: "확정 결정", action: "실행 항목" };
  for (const entry of [...state.entries].sort((a, b) => a.at.localeCompare(b.at) || a.id - b.id)) {
    const item = document.createElement("article"); item.className = "entry";
    const header = document.createElement("header"), who = document.createElement("b"), time = document.createElement("time");
    who.textContent = entry.speaker; time.textContent = new Date(entry.at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
    const text = document.createElement("p"); text.textContent = entry.text;
    const kind = document.createElement("span"); kind.className = "kind"; kind.textContent = kinds[entry.kind] || entry.kind;
    header.append(who, time); item.append(header, kind, text); list.append(item);
  }
  list.scrollTop = list.scrollHeight;
}
function drawStroke(stroke) {
  const canvas = $("board"), ctx = canvas.getContext("2d");
  ctx.strokeStyle = stroke.color; ctx.fillStyle = stroke.color; ctx.lineWidth = stroke.width; ctx.lineCap = ctx.lineJoin = "round";
  ctx.beginPath(); stroke.points.forEach(([x, y], i) => { i ? ctx.lineTo(x * canvas.width, y * canvas.height) : ctx.moveTo(x * canvas.width, y * canvas.height); });
  if (stroke.points.length === 1) { const [x, y] = stroke.points[0]; ctx.arc(x * canvas.width, y * canvas.height, stroke.width / 2, 0, Math.PI * 2); ctx.fill(); } else ctx.stroke();
}
function redrawBoard() { const canvas = $("board"); canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height); state.strokes.forEach(drawStroke); }
let drawing = null, drawingTimer = null;
function point(event) { const rect = $("board").getBoundingClientRect(); return [Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))]; }
function flushStroke(end = false) {
  if (!drawing) return;
  const stroke = { ...drawing, points: [...drawing.points] };
  if (stroke.points.length) rpc("stroke", stroke).catch(e => { toast(e.message); redrawBoard(); });
  drawing = end ? null : { ...drawing, points: drawing.points.slice(-1) };
  if (end) { clearInterval(drawingTimer); drawingTimer = null; }
}
$("board").onpointerdown = (event) => {
  if (!isPresenter()) return; $("board").setPointerCapture(event.pointerId);
  drawing = { color: $("pen-color").value, width: Number($("pen-width").value), points: [point(event)] }; drawStroke(drawing);
  drawingTimer = setInterval(() => { if (drawing?.points.length > 1) flushStroke(); }, 90);
};
$("board").onpointermove = (event) => { if (!drawing) return; if (!isPresenter()) return flushStroke(true); const next = point(event); drawStroke({ ...drawing, points: [drawing.points.at(-1), next] }); drawing.points.push(next); if (drawing.points.length >= 100) flushStroke(); };
$("board").onpointerup = () => flushStroke(true); $("board").onpointercancel = () => flushStroke(true);
async function downloadMinutes() {
  const blob = await (await api(`/api/rooms/${state.session.room_id}/minutes`, null, state.session.token)).blob();
  const url = URL.createObjectURL(blob), a = document.createElement("a"); a.href = url; a.download = `회의록-${state.session.code}.md`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 5000);
}
async function leave() {
  state.leaving = true; drawing = null; clearInterval(drawingTimer);
  state.ws?.close(); state.ws = null;
  state.publisher?.close(); state.publisher = null;
  for (const pc of state.peers.values()) pc.close(); state.peers.clear(); state.streams.clear();
  for (const key of ["micTrack", "cameraTrack", "shareTrack", "silentTrack", "blankTrack"]) { if (state[key]) { state[key].onended = null; state[key].stop(); state[key] = null; } }
  clearInterval(state.canvasTimer); await state.audioContext?.close().catch(() => {}); state.audioContext = null;
  state.local = null; state.session = null; state.room = null; state.entries = []; state.strokes = [];
  $("invite-link").value = ""; $("host-invite").hidden = true;
  $("remote-audio").replaceChildren(); $("grid").replaceChildren(); $("focus-video").srcObject = null;
  $("lobby").hidden = false; $("conference").hidden = true; $("footer").hidden = false; $("connection-label").textContent = "나의 회의 공간";
  // Every new entry begins with privacy-preserving device defaults.
  for (const key of ["pref-mic", "pref-speaker", "pref-camera"]) $(key).checked = false;
  state.mic = state.speaker = state.camera = false;
}
$("join-form").onsubmit = enter;
$("check-server").onclick = safeAction(checkServer);
$("server").onchange = safeAction(checkServer);
$("join-tab").onclick = () => setCreate(false); $("create-tab").onclick = () => setCreate(true);
$("mode").onchange = updateMinutesOption;
for (const [id, action] of [["toggle-mic", toggleMic], ["toggle-speaker", toggleSpeaker], ["toggle-camera", toggleCamera], ["share", share]]) {
  $(id).onclick = safeAction(async () => { $(id).disabled = true; try { await action(); } finally { $(id).disabled = id === "share" && !isPresenter(); } });
}
$("hand").onclick = safeAction(() => rpc("hand"));
$("toggle-minutes").onclick = safeAction(() => rpc("minutes", { enabled: !state.room.minutes_enabled }));
$("clear-board").onclick = safeAction(() => rpc("clear_board"));
$("leave").onclick = safeAction(leave);
$("copy-code").onclick = safeAction(async () => { await navigator.clipboard.writeText(`서버: ${serverURL()}\n접속 ID: ${state.session.code}`); toast("서버 주소와 방 접속 ID를 복사했습니다."); });
$("copy-invite").onclick = safeAction(copyInvitation);
$("invite-link").onclick = () => $("invite-link").select();
$("download").onclick = safeAction(downloadMinutes);
$("fullscreen").onclick = safeAction(() => document.fullscreenElement ? document.exitFullscreen() : $("workspace").requestFullscreen());
$("note-form").onsubmit = safeAction(async event => { event.preventDefault(); await rpc("note", { text: $("note-text").value, kind: $("note-kind").value }); $("note-text").value = ""; });
document.querySelectorAll("[data-view]").forEach(button => button.onclick = () => setView(button.dataset.view));
for (const panel of ["people", "notes"]) $(`${panel}-tab`).onclick = () => { for (const name of ["people", "notes"]) { $(`${name}-panel`).hidden = name !== panel; $(`${name}-tab`).classList.toggle("active", name === panel); } };
setInterval(() => {
  if (!state.room) return;
  const elapsed = Math.max(0, Math.floor((Date.now() - Date.parse(state.room.created_at)) / 1000));
  $("elapsed").textContent = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
}, 1000);
window.addEventListener("beforeunload", () => state.ws?.close());
window.addEventListener("hashchange", () => {
  if (state.busy) return;
  if (state.session) { toast("다른 초대 링크로 참여하려면 현재 회의에서 나간 뒤 링크를 다시 열어 주세요."); return; }
  setCreate(false); loadInvitation(); safeAction(checkServer)();
});
let saved = {}; try { saved = JSON.parse(localStorage.getItem("moa-settings") || "{}"); } catch (_) { /* No saved settings */ }
$("server").value = saved.server || location.origin; $("name").value = saved.name || "";
setCreate(false); loadInvitation(); safeAction(checkServer)();
