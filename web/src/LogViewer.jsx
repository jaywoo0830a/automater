import { useState, useEffect, useRef } from "react";
import { getCampaign, streamLogs } from "./api";

export default function LogViewer({ campaignId }) {
  const [lines, setLines] = useState([]);
  const [live, setLive] = useState(false);
  const outputRef = useRef();

  useEffect(() => {
    setLines([]);
    setLive(true);

    let wsReceived = false;

    const close = streamLogs(
      campaignId,
      (line) => {
        wsReceived = true;
        setLines((prev) => [...prev, line]);
      },
      () => {
        setLive(false);
        // WebSocket에서 로그를 못 받았으면 REST로 가져오기
        if (!wsReceived) {
          getCampaign(campaignId).then((data) => {
            if (data.recent_logs?.length) {
              setLines(data.recent_logs);
            }
          }).catch(() => {});
        }
      },
    );
    return close;
  }, [campaignId]);

  useEffect(() => {
    const el = outputRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <div className="log">
      <div className="log__container">
        <header className="log__header">
          <span className="log__title">
            <code>{campaignId}</code> 로그
          </span>
          {live && <span className="log__live">LIVE</span>}
        </header>
        <pre ref={outputRef} className="log__output">
          {lines.join("")}
        </pre>
      </div>
    </div>
  );
}
