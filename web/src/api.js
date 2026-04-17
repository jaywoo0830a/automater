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

export function uploadCampaign(file, name = "", onProgress) {
  // fetch 는 업로드 progress 이벤트를 지원하지 않으므로 XHR 사용.
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    if (name) form.append("name", name);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/campaigns");
    const hs = headers();
    for (const k in hs) xhr.setRequestHeader(k, hs[k]);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText); } catch {}
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body);
      } else {
        const msg = body.detail
          ? `${body.error || xhr.statusText}\n\n${body.detail}`
          : (body.error || xhr.statusText);
        const e = new Error(msg);
        e.detail = body.detail || "";
        e.status = xhr.status;
        reject(e);
      }
    };
    xhr.onerror = () => reject(new Error("network error"));
    xhr.send(form);
  });
}

export async function validateCampaign(campaignId) {
  const res = await fetch(`/campaigns/${campaignId}/validate`, {
    method: "POST",
    headers: headers(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = new Error(data.detail || data.error || res.statusText);
    e.detail = data.detail || "";
    e.status = res.status;
    throw e;
  }
  return data;
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
    const msg = err.detail
      ? `${err.error || res.statusText}\n\n${err.detail}`
      : (err.error || res.statusText);
    const e = new Error(msg);
    e.detail = err.detail || "";
    e.status = res.status;
    throw e;
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

export function streamVncLogs(sessionId, onLine, onClose) {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/sessions/vnc/${sessionId}/logs`);
  ws.onmessage = (e) => onLine(e.data);
  ws.onclose = () => onClose?.();
  ws.onerror = () => onClose?.();
  return () => ws.close();
}

// ---------------------------------------------------------------------------
// Observer
// ---------------------------------------------------------------------------

export async function getObserverStatus() {
  const res = await fetch("/observer/status", { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function getObserverCampaigns() {
  const res = await fetch("/observer/campaigns", { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function getObserverCampaign(id) {
  const res = await fetch(`/observer/campaigns/${id}`, { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function getObserverWorkers() {
  const res = await fetch("/observer/workers", { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function getObserverSchedules(status = "", limit = 50) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("limit", String(limit));
  const res = await fetch(`/observer/schedules?${params}`, { headers: headers() });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}
