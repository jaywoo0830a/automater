import { useState, useEffect } from "react";
import { listCampaigns, cancelCampaign } from "./api";

export default function CampaignList({ refreshKey, onSelect, selected, onRefresh }) {
  const [campaigns, setCampaigns] = useState([]);

  useEffect(() => {
    listCampaigns().then(setCampaigns).catch(() => {});
  }, [refreshKey]);

  useEffect(() => {
    const hasActive = campaigns.some((c) => ["queued", "running", "pending_sessions"].includes(c.status));
    if (!hasActive) return;
    const id = setInterval(() => {
      listCampaigns().then(setCampaigns).catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, [campaigns]);

  async function handleCancel(e, id) {
    e.stopPropagation();
    try {
      await cancelCampaign(id);
      onRefresh?.();
    } catch (err) {
      alert(err.message);
    }
  }

  if (!campaigns.length) {
    return <p className="campaigns__empty">캠페인 없음</p>;
  }

  return (
    <div className="campaigns">
      <div className="campaigns__header">
        <span className="campaigns__count">{campaigns.length}개 캠페인</span>
      </div>
      <table className="campaigns__table">
        <thead>
          <tr>
            <th className="campaigns__th">ID</th>
            <th className="campaigns__th">상태</th>
            <th className="campaigns__th">로그</th>
            <th className="campaigns__th"></th>
          </tr>
        </thead>
        <tbody>
          {campaigns.map((c) => {
            const rowCls = `campaigns__row${selected === c.id ? " campaigns__row--selected" : ""}`;
            return (
              <tr key={c.id} className={rowCls} onClick={() => onSelect(c.id, c.status)}>
                <td className="campaigns__td">
                  <code className="campaigns__id">{c.id}</code>
                </td>
                <td className="campaigns__td">
                  <span className={`badge badge--${c.status}`}>{c.status}</span>
                </td>
                <td className="campaigns__td">{c.log_length}줄</td>
                <td className="campaigns__td">
                  {(c.status === "queued" || c.status === "running") && (
                    <button className="btn btn--danger" onClick={(e) => handleCancel(e, c.id)}>
                      중단
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
