import { useState, useEffect } from "react";
import { getCampaign, cancelCampaign, validateCampaign } from "./api";
import LogViewer from "./LogViewer";
import SessionSetup from "./SessionSetup";

export default function CampaignPage({ campaignId, onBack, onLogout }) {
  const [campaign, setCampaign] = useState(null);
  const [validateStatus, setValidateStatus] = useState(null); // null | {ok, msg}

  useEffect(() => {
    getCampaign(campaignId).then(setCampaign).catch(() => {});
  }, [campaignId]);

  // poll status
  useEffect(() => {
    if (!campaign) return;
    if (!["pending_sessions", "queued", "running"].includes(campaign.status)) return;
    const id = setInterval(() => {
      getCampaign(campaignId).then(setCampaign).catch(() => {});
    }, 3000);
    return () => clearInterval(id);
  }, [campaign?.status, campaignId]);

  async function handleCancel() {
    try {
      await cancelCampaign(campaignId);
      getCampaign(campaignId).then(setCampaign).catch(() => {});
    } catch (e) {
      alert(e.message);
    }
  }

  async function handleValidate() {
    setValidateStatus({ ok: null, msg: "Validating..." });
    try {
      await validateCampaign(campaignId);
      setValidateStatus({ ok: true, msg: "✓ Config valid" });
    } catch (e) {
      setValidateStatus({ ok: false, msg: e.message });
    }
  }

  function handleExecuted() {
    getCampaign(campaignId).then(setCampaign).catch(() => {});
  }

  if (!campaign) {
    return <div className="app"><p>Loading...</p></div>;
  }

  const validateCls = validateStatus
    ? `validate__status${validateStatus.ok === true ? " validate__status--ok"
      : validateStatus.ok === false ? " validate__status--err" : ""}`
    : "";

  return (
    <main className="app">
      <header className="app__header">
        <div className="app__nav">
          <button className="btn btn--ghost" onClick={onBack}>&larr; Back</button>
          <h1 className="app__title">{campaign.name}</h1>
          <span className={`badge badge--${campaign.status}`}>{campaign.status}</span>
        </div>
        <div className="app__actions">
          {campaign.status === "pending_sessions" && (
            <button className="btn btn--ghost" onClick={handleValidate}>Validate</button>
          )}
          {["queued", "running"].includes(campaign.status) && (
            <button className="btn btn--danger" onClick={handleCancel}>Cancel</button>
          )}
          <button className="btn btn--ghost" onClick={onLogout}>Logout</button>
        </div>
      </header>

      {validateStatus && (
        <section className="app__section">
          <pre className={validateCls}>{validateStatus.msg}</pre>
        </section>
      )}

      {campaign.status === "pending_sessions" && (
        <section className="app__section">
          <SessionSetup campaignId={campaignId} onExecuted={handleExecuted} />
        </section>
      )}

      {campaign.status !== "pending_sessions" && (
        <section className="app__section">
          <LogViewer campaignId={campaignId} />
        </section>
      )}
    </main>
  );
}
