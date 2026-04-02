import { useState } from "react";
import { isLoggedIn, clearApiKey } from "./api";
import Login from "./Login";
import Upload from "./Upload";
import CampaignList from "./CampaignList";
import LogViewer from "./LogViewer";
import SessionSetup from "./SessionSetup";

export default function App() {
  const [authed, setAuthed] = useState(isLoggedIn());
  const [selected, setSelected] = useState(null);
  const [selectedStatus, setSelectedStatus] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = () => setRefreshKey((k) => k + 1);

  function handleLogout() {
    clearApiKey();
    setAuthed(false);
    setSelected(null);
  }

  function handleSelect(id, status) {
    setSelected(id);
    setSelectedStatus(status);
  }

  function handleExecuted() {
    setSelectedStatus("queued");
    refresh();
  }

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />;
  }

  return (
    <main className="app">
      <header className="app__header">
        <h1 className="app__title">Automator</h1>
        <button className="btn btn--ghost" onClick={handleLogout}>Logout</button>
      </header>

      <section className="app__section">
        <Upload onUploaded={refresh} />
      </section>

      <section className="app__section">
        <CampaignList
          refreshKey={refreshKey}
          onSelect={handleSelect}
          selected={selected}
          onRefresh={refresh}
        />
      </section>

      {selected && selectedStatus === "pending_sessions" && (
        <section className="app__section">
          <SessionSetup campaignId={selected} onExecuted={handleExecuted} />
        </section>
      )}

      {selected && selectedStatus !== "pending_sessions" && (
        <section className="app__section">
          <LogViewer campaignId={selected} />
        </section>
      )}
    </main>
  );
}
