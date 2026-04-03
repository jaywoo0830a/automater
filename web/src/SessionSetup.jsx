import { useState, useEffect, useCallback } from "react";
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
  const [currentVnc, setCurrentVnc] = useState(null); // { username, sessionId, wsPort, status }
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState("");

  // poll campaign session status
  const refreshSessions = useCallback(async () => {
    try {
      const data = await getCampaignSessions(campaignId);
      setAccounts(data.accounts || []);
      setAllReady(data.all_ready);
      return data;
    } catch { return null; }
  }, [campaignId]);

  useEffect(() => {
    refreshSessions();
    const id = setInterval(refreshSessions, 3000);
    return () => clearInterval(id);
  }, [refreshSessions]);

  // 자동 순차 로그인: missing 계정 중 첫 번째를 자동으로 VNC 시작
  useEffect(() => {
    if (currentVnc || allReady || accounts.length === 0) return;
    const next = accounts.find((a) => !a.has_session);
    if (next) startVnc(next.username);
  }, [accounts, currentVnc, allReady]);

  // poll VNC session
  useEffect(() => {
    if (!currentVnc?.sessionId) return;
    const id = setInterval(async () => {
      try {
        const data = await getVncSession(currentVnc.sessionId);
        if (data.status === "ready" && !currentVnc.wsPort) {
          setCurrentVnc((prev) => ({ ...prev, wsPort: data.websockify_port, status: "ready" }));
        } else if (data.status === "logged_in") {
          // 완료 → 다음 계정으로
          setCurrentVnc(null);
          refreshSessions();
        } else if (data.status === "failed") {
          setCurrentVnc((prev) => ({ ...prev, status: "failed", error: data.error }));
        }
      } catch {}
    }, 1500);
    return () => clearInterval(id);
  }, [currentVnc?.sessionId, currentVnc?.wsPort]);

  async function startVnc(username) {
    setError("");
    try {
      const data = await startCampaignVnc(campaignId, username);
      setCurrentVnc({ username, sessionId: data.session_id, wsPort: null, status: "starting" });
    } catch (e) {
      setError(e.message);
    }
  }

  function handleSkip() {
    if (currentVnc?.sessionId) {
      deleteVncSession(currentVnc.sessionId).catch(() => {});
    }
    setCurrentVnc(null);
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

  const vncUrl = currentVnc?.wsPort
    ? `${window.location.origin}/vnc/${currentVnc.wsPort}/vnc.html?autoconnect=true&resize=scale&path=vnc/${currentVnc.wsPort}/websockify`
    : "";

  const doneCount = accounts.filter((a) => a.has_session).length;
  const totalCount = accounts.length;

  return (
    <div className="setup">
      <div className="setup__header">
        <span className="setup__title">
          Session Setup ({doneCount}/{totalCount})
        </span>
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

      {/* 계정 상태 목록 */}
      <div className="setup__accounts">
        {accounts.map((acc) => (
          <span
            key={acc.username}
            className={`setup__account ${acc.has_session ? "setup__account--ready" : "setup__account--missing"} ${currentVnc?.username === acc.username ? "setup__account--active" : ""}`}
          >
            {acc.username}
          </span>
        ))}
      </div>

      {error && <p className="setup__error">{error}</p>}

      {/* VNC 상태 */}
      {currentVnc && currentVnc.status === "starting" && (
        <div className="setup__vnc-status">
          Starting browser for <code>{currentVnc.username}</code>...
        </div>
      )}

      {currentVnc && currentVnc.status === "ready" && (
        <div className="setup__vnc">
          <div className="setup__vnc-header">
            <span>
              <code>{currentVnc.username}</code>
              {" "}&mdash;{" "}
              <kbd>Ctrl+V</kbd> (ID) → <kbd>Ctrl+V</kbd> (PW) → Login
            </span>
            <button className="btn btn--ghost" onClick={handleSkip}>skip</button>
          </div>
          <iframe
            className="setup__viewer"
            src={vncUrl}
            title="Remote Browser"
            allow="fullscreen"
          />
        </div>
      )}

      {currentVnc && currentVnc.status === "failed" && (
        <div className="setup__vnc-status setup__error">
          Failed: {currentVnc.error}
          <button className="btn btn--ghost" onClick={() => setCurrentVnc(null)}>retry</button>
        </div>
      )}
    </div>
  );
}
