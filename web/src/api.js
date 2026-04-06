function getApiKey() {
  return localStorage.getItem("api_key") || "";
}

export function setApiKey(key) {
  localStorage.setItem("api_key", key);
}

export function clearApiKey() {
  localStorage.removeItem("api_key");
}

export function isLoggedIn() {
  return !!getApiKey();
}

function headers() {
  const h = {};
  const key = getApiKey();
  if (key) h["X-API-Key"] = key;
  return h;
}

export async function verifyApiKey(key) {
  const res = await fetch("/campaigns", {
    headers: { "X-API-Key": key },
  });
  return res.ok;
}

export async function uploadCampaign(file, name = "") {
  const form = new FormData();
  form.append("file", file);
  if (name) form.append("name", name);
  const res = await fetch("/campaigns", {
    method: "POST",
    headers: headers(),
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

export async function listCampaigns() {
  const res = await fetch("/campaigns", { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function getCampaign(id) {
  const res = await fetch(`/campaigns/${id}`, { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function cancelCampaign(id) {
  const res = await fetch(`/campaigns/${id}`, {
    method: "DELETE",
    headers: headers(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Campaign sessions + execution
// ---------------------------------------------------------------------------

export async function getCampaignSessions(campaignId) {
  const res = await fetch(`/campaigns/${campaignId}/sessions`, { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function executeCampaign(campaignId) {
  const res = await fetch(`/campaigns/${campaignId}/execute`, {
    method: "POST",
    headers: headers(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

export async function startCampaignVnc(campaignId, username, mode = "auto") {
  const res = await fetch(`/campaigns/${campaignId}/sessions/vnc`, {
    method: "POST",
    headers: { ...headers(), "Content-Type": "application/json" },
    body: JSON.stringify({ username, mode }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// VNC session status/stop
// ---------------------------------------------------------------------------

export async function getVncSession(sessionId) {
  const res = await fetch(`/sessions/vnc/${sessionId}`, { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function deleteVncSession(sessionId) {
  const res = await fetch(`/sessions/vnc/${sessionId}`, {
    method: "DELETE",
    headers: headers(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Log streaming
// ---------------------------------------------------------------------------

export function streamLogs(id, onLine, onClose) {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/campaigns/${id}/logs`);
  ws.onmessage = (e) => onLine(e.data);
  ws.onclose = () => onClose?.();
  ws.onerror = () => onClose?.();
  return () => ws.close();
}
