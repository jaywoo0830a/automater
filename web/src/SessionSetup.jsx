import { useState, useEffect, useCallback } from "react";
import {
  getCampaignSessions,
  executeCampaign,
  startCampaignVnc,
  getVncSession,
  deleteVncSession,
  streamVncLogs,
} from "./api";

export default function SessionSetup({ campaignId, onExecuted }) {
  const [accounts, setAccounts] = useState([]);
  const [allReady, setAllReady] = useState(false);
  const [currentVnc, setCurrentVnc] = useState(null); // { username, sessionId, wsPort, status, mode }
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState("");
  const [loginMode, setLoginMode] = useState("auto"); // "auto" | "manual"
  const [logLines, setLogLines] = useState([]);

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

  // 자동 순차 로그인: missing 계정 중 첫 번째를 선택된 모드로 시작
  useEffect(() => {
    if (currentVnc || allReady || accounts.length === 0) return;
    const next = accounts.find((a) => !a.has_session);
    if (next) startVnc(next.username, loginMode);
  }, [accounts, currentVnc, allReady, loginMode]);

  // stream VNC logs for current session
  useEffect(() => {
    if (!currentVnc?.sessionId) {
      setLogLines([]);
      return;
    }
    setLogLines([]);
    const close = streamVncLogs(
      currentVnc.sessionId,
      (line) => setLogLines((prev) => [...prev, line]),
      () => {},
    );
    return close;
  }, [currentVnc?.sessionId]);

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

  async function startVnc(username, mode) {
    setError("");
    try {
      const data = await startCampaignVnc(campaignId, username, mode);
      setCurrentVnc({
        username,
        sessionId: data.session_id,
        wsPort: null,
        status: "starting",
        mode: data.mode || mode,
      });
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

  // 모드 토글은 진행 중 세션이 없을 때만 가능
  const modeToggleDisabled = currentVnc !== null;

  return (
    <div className="setup">
      <div className="setup__header">
        <span className="setup__title">
          Session Setup ({doneCount}/{totalCount})
        </span>

        {/* 로그인 모드 토글 */}
        <div className="setup__mode" role="radiogroup" aria-label="로그인 모드">
          <label className={`setup__mode-option ${loginMode === "auto" ? "setup__mode-option--active" : ""}`}>
            <input
              type="radio"
              name="loginMode"
              value="auto"
              checked={loginMode === "auto"}
              onChange={() => setLoginMode("auto")}
              disabled={modeToggleDisabled}
            />
            세션 준비 (자동)
          </label>
          <label className={`setup__mode-option ${loginMode === "manual" ? "setup__mode-option--active" : ""}`}>
            <input
              type="radio"
              name="loginMode"
              value="manual"
              checked={loginMode === "manual"}
              onChange={() => setLoginMode("manual")}
              disabled={modeToggleDisabled}
            />
            수동 세션 준비
          </label>
        </div>

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

      {/* 모드 설명 */}
      <p className="setup__mode-desc">
        {loginMode === "auto"
          ? "자동 로그인: Playwright 키보드로 ID/PW 자동 입력. CAPTCHA/2차 인증 시에만 직접 처리하세요."
          : "수동 로그인: 브라우저만 열리며 ID/PW를 직접 입력하셔야 합니다."}
      </p>

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

      {error && <pre className="setup__error setup__error--block">{error}</pre>}

      {/* VNC 상태 */}
      {currentVnc && currentVnc.status === "starting" && (
        <div className="setup__vnc-status">
          Starting browser for <code>{currentVnc.username}</code>
          {" ("}{currentVnc.mode === "auto" ? "자동" : "수동"}{")"}...
        </div>
      )}

      {currentVnc && currentVnc.status === "ready" && (
        <div className="setup__vnc">
          <div className="setup__vnc-header">
            <span>
              <code>{currentVnc.username}</code>
              {" "}&mdash;{" "}
              {currentVnc.mode === "auto"
                ? "자동 로그인 중... CAPTCHA/2차 인증이 뜨면 직접 처리해주세요."
                : "브라우저에서 직접 ID/PW를 입력해주세요."}
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

      {currentVnc && logLines.length > 0 && (
        <pre className="setup__log">{logLines.join("")}</pre>
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
