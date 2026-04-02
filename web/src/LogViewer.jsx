import { useState, useEffect, useRef } from "react";
import { getCampaign, streamLogs } from "./api";

export default function LogViewer({ campaignId }) {
  const [lines, setLines] = useState([]);
  const [live, setLive] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const outputRef = useRef();
  const baseCountRef = useRef(0);

  useEffect(() => {
    setLines([]);
    setLive(true);
    setAutoScroll(true);
    baseCountRef.current = 0;

    // 1. REST로 전체 로그 가져오기
    getCampaign(campaignId).then((data) => {
      const existing = data.logs || [];
      baseCountRef.current = existing.length;
      setLines(existing);
    }).catch(() => {});

    // 2. WebSocket — REST 이후 줄만 추가
    let wsCount = 0;
    const close = streamLogs(
      campaignId,
      (line) => {
        wsCount++;
        if (wsCount > baseCountRef.current) {
          setLines((prev) => [...prev, line]);
        }
      },
      () => setLive(false),
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

  return (
    <div className="log">
      <div className="log__container">
        <header className="log__header">
          <span className="log__title">
            <code>{campaignId}</code> log ({lines.length} lines)
          </span>
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
        </header>
        <pre ref={outputRef} className="log__output" onScroll={handleScroll}>
          {lines.join("")}
        </pre>
      </div>
    </div>
  );
}
