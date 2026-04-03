import { useState, useEffect } from "react";
import { listCampaigns } from "./api";

export default function CampaignList({ refreshKey, onSelect, onRefresh }) {
  const [campaigns, setCampaigns] = useState([]);

  useEffect(() => {
    listCampaigns().then(setCampaigns).catch(() => {});
  }, [refreshKey]);

  useEffect(() => {
    const hasActive = campaigns.some((c) =>
      ["queued", "running", "pending_sessions"].includes(c.status)
    );
    if (!hasActive) return;
    const id = setInterval(() => {
      listCampaigns().then(setCampaigns).catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, [campaigns]);

  const sorted = [...campaigns].sort((a, b) => b.created_at - a.created_at);

  if (!sorted.length) {
    return <p className="campaigns__empty">No campaigns</p>;
  }

  return (
    <div className="campaigns">
      <div className="campaigns__grid">
        {sorted.map((c) => (
          <article
            key={c.id}
            className="campaigns__card"
            onClick={() => onSelect(c.id)}
          >
            <div className="campaigns__card-header">
              <span className="campaigns__card-name">{c.name}</span>
              <span className={`badge badge--${c.status}`}>{c.status}</span>
            </div>
            <div className="campaigns__card-meta">
              <code>{c.id}</code>
              <span>{c.log_length} lines</span>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
