const API_KEY = localStorage.getItem("api_key") || "";

function headers() {
  const h = {};
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

export async function uploadCampaign(file) {
  const form = new FormData();
  form.append("file", file);
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

export function streamLogs(id, onLine, onClose) {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/campaigns/${id}/logs`);
  ws.onmessage = (e) => onLine(e.data);
  ws.onclose = () => onClose?.();
  ws.onerror = () => onClose?.();
  return () => ws.close();
}
