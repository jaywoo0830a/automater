import { useState, useEffect, useRef } from "react";
import { startVncSession, getVncSession, deleteVncSession } from "./api";

export default function VncLogin({ onClose }) {
  const [phase, setPhase] = useState("form"); // form | starting | ready | done | error
  const [sessionId, setSessionId] = useState(null);
  const [wsPort, setWsPort] = useState(null);
  const [message, setMessage] = useState("");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [blogId, setBlogId] = useState("");

  // cleanup on unmount
  useEffect(() => {
    return () => {
      if (sessionId) deleteVncSession(sessionId).catch(() => {});
    };
  }, [sessionId]);

  // poll session status
  useEffect(() => {
    if (!sessionId || phase === "done" || phase === "error") return;

    const id = setInterval(async () => {
      try {
        const data = await getVncSession(sessionId);
        if (data.status === "ready" && phase === "starting") {
          setWsPort(data.websockify_port);
          setPhase("ready");
        } else if (data.status === "logged_in") {
          setPhase("done");
          setMessage(`${data.username} login complete`);
        } else if (data.status === "failed") {
          setPhase("error");
          setMessage(data.error || "login failed");
        }
      } catch {}
    }, 1500);

    return () => clearInterval(id);
  }, [sessionId, phase]);

  async function handleStart(e) {
    e.preventDefault();
    if (!username || !password) return;

    setPhase("starting");
    setMessage("");

    try {
      const data = await startVncSession({
        username,
        password,
        blog_id: blogId || username,
      });
      setSessionId(data.session_id);
    } catch (err) {
      setPhase("error");
      setMessage(err.message);
    }
  }

  function handleCancel() {
    if (sessionId) deleteVncSession(sessionId).catch(() => {});
    onClose?.();
  }

  // noVNC URL — websockify가 /usr/share/novnc 를 서빙함
  const vncUrl = wsPort
    ? `http://${window.location.hostname}:${wsPort}/vnc.html?autoconnect=true&resize=scale`
    : "";

  return (
    <div className="vnc">
      <div className="vnc__header">
        <span className="vnc__title">Remote Login</span>
        <button className="btn btn--ghost" onClick={handleCancel}>
          {phase === "done" ? "close" : "cancel"}
        </button>
      </div>

      {phase === "form" && (
        <form className="vnc__form" onSubmit={handleStart}>
          <input
            className="vnc__input"
            type="text"
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
          <input
            className="vnc__input"
            type="password"
            placeholder="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <input
            className="vnc__input"
            type="text"
            placeholder="blog_id (optional)"
            value={blogId}
            onChange={(e) => setBlogId(e.target.value)}
          />
          <button className="vnc__submit" type="submit">Start</button>
        </form>
      )}

      {phase === "starting" && (
        <div className="vnc__status">Starting browser...</div>
      )}

      {phase === "ready" && (
        <>
          <div className="vnc__hint">
            ID field click &rarr; <kbd>Ctrl+V</kbd> (username) &rarr;
            PW field click &rarr; <kbd>Ctrl+V</kbd> (password) &rarr;
            Login button click
          </div>
          <iframe
            className="vnc__viewer"
            src={vncUrl}
            title="Remote Browser"
            allow="fullscreen"
            allowFullScreen
          />
        </>
      )}

      {phase === "done" && (
        <div className="vnc__status vnc__status--success">{message}</div>
      )}

      {phase === "error" && (
        <div className="vnc__status vnc__status--error">{message}</div>
      )}
    </div>
  );
}
