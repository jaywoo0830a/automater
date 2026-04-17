import { useState, useEffect } from "react";
import {
  getObserverStatus,
  getObserverCampaigns,
  getObserverCampaign,
  getObserverWorkers,
} from "./api";

function StatusBar({ status }) {
  if (!status) return null;
  return (
    <div className="obs__status-bar">
      <div className="obs__stat">
        <span className="obs__stat-value obs__stat-value--due">{status.due}</span>
        <span className="obs__stat-label">Due</span>
      </div>
      <div className="obs__stat">
        <span className="obs__stat-value obs__stat-value--upcoming">{status.upcoming}</span>
        <span className="obs__stat-label">Upcoming</span>
      </div>
      <div className="obs__stat">
        <span className="obs__stat-value obs__stat-value--done">{status.done}</span>
        <span className="obs__stat-label">Done</span>
      </div>
      <div className="obs__stat">
        <span className="obs__stat-value obs__stat-value--skipped">{status.skipped}</span>
        <span className="obs__stat-label">Skipped</span>
      </div>
    </div>
  );
}

function WorkerGrid({ workers }) {
  if (!workers || workers.length === 0) {
    return <p className="obs__empty">No active workers</p>;
  }
  return (
    <div className="obs__workers">
      {workers.map((w) => (
        <div key={w.ws_port} className="obs__worker-card">
          <div className="obs__worker-header">
            <span className="obs__worker-id">Worker {w.worker_id}</span>
            <span className={`badge badge--${w.status === "running" ? "running" : "completed"}`}>
              {w.status}
            </span>
          </div>
          <div className="obs__worker-meta">
            <span>{w.keyword || "idle"}</span>
            <span className="obs__worker-blog">{w.blog_id}</span>
          </div>
          <iframe
            className="obs__worker-vnc"
            src={`/vnc/${w.ws_port}/vnc.html?autoconnect=true&resize=scale&reconnect=true`}
            title={`Worker ${w.worker_id}`}
          />
        </div>
      ))}
    </div>
  );
}

function CampaignRow({ campaign, onSelect }) {
  const pct = campaign.schedules_total
    ? Math.round((campaign.schedules_done / campaign.schedules_total) * 100)
    : 0;
  return (
    <tr className="obs__row" onClick={() => onSelect(campaign.id)}>
      <td className="obs__cell">{campaign.keyword}</td>
      <td className="obs__cell obs__cell--mono">{campaign.blog_id}</td>
      <td className="obs__cell">{campaign.published_at ? fmtTime(campaign.published_at) : "-"}</td>
      <td className="obs__cell">
        <div className="obs__progress">
          <div className="obs__progress-bar" style={{ width: `${pct}%` }} />
          <span className="obs__progress-text">{campaign.schedules_done}/{campaign.schedules_total}</span>
        </div>
      </td>
    </tr>
  );
}

function ScheduleTimeline({ schedules }) {
  if (!schedules || schedules.length === 0) return <p className="obs__empty">No schedules</p>;
  return (
    <div className="obs__timeline">
      {schedules.map((s) => (
        <div key={s.id} className={`obs__tl-item obs__tl-item--${s.status}`}>
          <div className="obs__tl-dot" />
          <div className="obs__tl-content">
            <span className="obs__tl-time">{fmtTime(s.scheduled_at)}</span>
            <span className={`badge badge--${s.status === "done" ? "completed" : s.status === "skipped" ? "failed" : "queued"}`}>
              {s.status}
            </span>
            {s.observation && (
              <div className="obs__tl-obs">
                <span className="obs__tl-rank">
                  {s.observation.rank != null ? `#${s.observation.rank}` : "not found"}
                </span>
                {s.observation.dwell_seconds && (
                  <span className="obs__tl-dwell">{Math.round(s.observation.dwell_seconds)}s dwell</span>
                )}
                {s.observation.scroll_pct != null && (
                  <span className="obs__tl-scroll">{Math.round(s.observation.scroll_pct * 100)}% scroll</span>
                )}
                <span className="obs__tl-meta">{s.observation.viewport} | {s.observation.session_ip}</span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function fmtTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("ko-KR", {
    month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function ObserverPage({ onBack, onLogout }) {
  const [status, setStatus] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [workers, setWorkers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 5_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (selected != null) {
      getObserverCampaign(selected).then(setDetail).catch((e) => setError(e.message));
    } else {
      setDetail(null);
    }
  }, [selected]);

  async function loadData() {
    try {
      const [s, c, w] = await Promise.all([
        getObserverStatus(),
        getObserverCampaigns(),
        getObserverWorkers(),
      ]);
      setStatus(s);
      setCampaigns(c);
      setWorkers(w);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }

  if (detail) {
    return (
      <main className="app">
        <header className="app__header">
          <div className="app__nav">
            <button className="btn btn--ghost" onClick={() => setSelected(null)}>Back</button>
            <h1 className="app__title">{detail.keyword}</h1>
          </div>
          <button className="btn btn--ghost" onClick={onLogout}>Logout</button>
        </header>

        <section className="obs__detail">
          <div className="obs__detail-meta">
            <span>Blog: <code>{detail.blog_id}</code></span>
            <span>Published: {fmtTime(detail.published_at)}</span>
            <span>Platform: {detail.platform}</span>
          </div>
          <h2 className="obs__subtitle">Schedule Timeline</h2>
          <ScheduleTimeline schedules={detail.schedules} />
        </section>
      </main>
    );
  }

  return (
    <main className="app">
      <header className="app__header">
        <div className="app__nav">
          <button className="btn btn--ghost" onClick={onBack}>Back</button>
          <h1 className="app__title">Observer</h1>
        </div>
        <button className="btn btn--ghost" onClick={onLogout}>Logout</button>
      </header>

      {error && <p className="obs__error">{error}</p>}

      <StatusBar status={status} />

      <section className="app__section">
        <h2 className="obs__subtitle">Active Workers</h2>
        <WorkerGrid workers={workers} />
      </section>

      <section className="app__section">
        <h2 className="obs__subtitle">Campaigns</h2>
        {campaigns.length === 0 ? (
          <p className="obs__empty">No observer campaigns yet</p>
        ) : (
          <table className="obs__table">
            <thead>
              <tr>
                <th className="obs__th">Keyword</th>
                <th className="obs__th">Blog ID</th>
                <th className="obs__th">Published</th>
                <th className="obs__th">Progress</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <CampaignRow key={c.id} campaign={c} onSelect={setSelected} />
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
