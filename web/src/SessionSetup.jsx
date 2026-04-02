import { useState, useEffect } from "react";
import {
  getCampaignSessions,
  executeCampaign,
  startCampaignVnc,
  getVncSession,
  deleteVncSession,
} from "./api";

export default function SessionSetup({ campaignId, onExecuted }) {
  const [accounts, setAccounts] = useState([]);
  const [allReady, setAllReady] = useState(false);
  const [vncTarget, setVncTarget] = useState(null); // { username, sessionId, wsPort, status }
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState("");

  // poll session status
  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const data = await getCampaignSessions(campaignId);
        if (active) {
          setAccounts(data.accounts || []);
          setAllReady(data.all_ready);
        }
      } catch {}
    }
    poll();
    const id = setInterval(poll, 3000);
    return () => { active = false; clearInterval(id); };
  }, [campaignId]);

  // poll VNC session status
  useEffect(() => {
    if (!vncTarget?.sessionId) return;
    const id = setInterval(async () => {
      try {
        const data = await getVncSession(vncTarget.sessionId);
        if (data.status === "ready" && !vncTarget.wsPort) {
          setVncTarget((prev) => ({ ...prev, wsPort: data.websockify_port, status: "ready" }));
        } else if (data.status === "logged_in") {
          setVncTarget(null);
        } else if (data.status === "failed") {
          setVncTarget((prev) => ({ ...prev, status: "failed", error: data.error }));
        }
      } catch {}
    }, 1500);
    return () => clearInterval(id);
  }, [vncTarget?.sessionId, vncTarget?.wsPort]);

  async function handleLogin(username) {
    setError("");
    try {
      const data = await startCampaignVnc(campaignId, username);
      setVncTarget({ username, sessionId: data.session_id, wsPort: null, status: "starting" });
    } catch (e) {
      setError(e.message);
    }
  }

  function handleCancelVnc() {
    if (vncTarget?.sessionId) {
      deleteVncSession(vncTarget.sessionId).catch(() => {});
    }
    setVncTarget(null);
  }

  async function handleExecute() {
    setExecuting(true);
    setError("");
    try {
      await executeCampaign(campaignId);
      onExecuted?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setExecuting(false);
    }
  }

  const vncUrl = vncTarget?.wsPort
    ? `http://${window.location.hostname}:${vncTarget.wsPort}/vnc.html?autoconnect=true&resize=scale`
    : "";

  return (
    <div className="setup">
      <div className="setup__header">
        <span className="setup__title">Session Setup</span>
        {allReady && (
          <button
            className="setup__execute"
            onClick={handleExecute}
            disabled={executing}
          >
            {executing ? "Starting..." : "Execute Campaign"}
          </button>
        )}
      </div>

      <table className="setup__table">
        <thead>
          <tr>
            <th className="setup__th">Account</th>
            <th className="setup__th">Blog ID</th>
            <th className="setup__th">Session</th>
            <th className="setup__th"></th>
          </tr>
        </thead>
        <tbody>
          {accounts.map((acc) => (
            <tr key={acc.username} className="setup__row">
              <td className="setup__td">
                <code>{acc.username}</code>
              </td>
              <td className="setup__td">{acc.blog_id}</td>
              <td className="setup__td">
                {acc.has_session ? (
                  <span className="setup__ready">ready</span>
                ) : (
                  <span className="setup__missing">missing</span>
                )}
              </td>
              <td className="setup__td">
                {!acc.has_session && (
                  <button
                    className="btn btn--ghost"
                    onClick={() => handleLogin(acc.username)}
                    disabled={!!vncTarget}
                  >
                    Login
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {error && <p className="setup__error">{error}</p>}

      {vncTarget && vncTarget.status === "starting" && (
        <div className="setup__vnc-status">
          Starting browser for {vncTarget.username}...
          <button className="btn btn--ghost" onClick={handleCancelVnc}>cancel</button>
        </div>
      )}

      {vncTarget && vncTarget.status === "ready" && (
        <div className="setup__vnc">
          <div className="setup__vnc-header">
            <span>Logging in: <code>{vncTarget.username}</code></span>
            <span className="setup__hint">
              ID field &rarr; <kbd>Ctrl+V</kbd> &rarr;
              PW field &rarr; <kbd>Ctrl+V</kbd> &rarr;
              Login
            </span>
            <button className="btn btn--ghost" onClick={handleCancelVnc}>cancel</button>
          </div>
          <iframe
            className="setup__viewer"
            src={vncUrl}
            title="Remote Browser"
            allow="fullscreen"
            allowFullScreen
          />
        </div>
      )}

      {vncTarget && vncTarget.status === "failed" && (
        <div className="setup__vnc-status setup__error">
          Login failed: {vncTarget.error}
          <button className="btn btn--ghost" onClick={handleCancelVnc}>dismiss</button>
        </div>
      )}
    </div>
  );
}
