import { useState, useEffect, useRef } from "react";
import { getCampaign, streamLogs } from "./api";

export default function LogViewer({ campaignId }) {
  const [lines, setLines] = useState([]);
  const [live, setLive] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [vncPort, setVncPort] = useState(0);
  const [showVnc, setShowVnc] = useState(false);
  const outputRef = useRef();
  const baseCountRef = useRef(0);

  useEffect(() => {
    setLines([]);
    setLive(true);
    setAutoScroll(true);
    setVncPort(0);
    setShowVnc(false);
    baseCountRef.current = 0;

    getCampaign(campaignId).then((data) => {
      const existing = data.logs || [];
      baseCountRef.current = existing.length;
      setLines(existing);
      if (data.vnc_port && data.status === "running") {
        setVncPort(data.vnc_port);
      }
    }).catch(() => {});

    let wsCount = 0;
    const close = streamLogs(
      campaignId,
      (line) => {
        wsCount++;
        if (wsCount > baseCountRef.current) {
          setLines((prev) => [...prev, line]);
        }
        // VNC 포트 감지
        if (line.includes("[VNC] ws://")) {
          const match = line.match(/:(\d+)/);
          if (match) setVncPort(parseInt(match[1]));
        }
      },
      () => {
        setLive(false);
        setVncPort(0);
      },
    );
    return close;
  }, [campaignId]);

  useEffect(() => {
    const el = outputRef.current;
    if (el && autoScroll) el.scrollTop = el.scrollHeight;
  }, [lines, autoScroll]);

  function handleScroll() {
    const el = outputRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  }

  const vncUrl = vncPort
    ? `http://${window.location.hostname}:${vncPort}/vnc.html?autoconnect=true&resize=scale`
    : "";

  return (
    <div className="log">
      <div className="log__container">
        <header className="log__header">
          <span className="log__title">
            <code>{campaignId}</code> log ({lines.length} lines)
          </span>
          <span className="log__actions">
            {vncPort > 0 && (
              <button
                className="btn btn--ghost"
                onClick={() => setShowVnc(!showVnc)}
              >
                {showVnc ? "Hide Browser" : "Show Browser"}
              </button>
            )}
            {live && <span className="log__live">LIVE</span>}
            {!autoScroll && (
              <button
                className="btn btn--ghost"
                onClick={() => {
                  setAutoScroll(true);
                  const el = outputRef.current;
                  if (el) el.scrollTop = el.scrollHeight;
                }}
              >
                scroll to bottom
              </button>
            )}
          </span>
        </header>

        {showVnc && vncUrl && (
          <iframe
            className="log__vnc"
            src={vncUrl}
            title="Live Browser"
            allow="fullscreen"
            allowFullScreen
          />
        )}

        <pre ref={outputRef} className="log__output" onScroll={handleScroll}>
          {lines.join("")}
        </pre>
      </div>
    </div>
  );
}
