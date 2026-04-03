import { useState, useEffect } from "react";
import { isLoggedIn, clearApiKey, getCampaign } from "./api";
import Login from "./Login";
import Upload from "./Upload";
import CampaignList from "./CampaignList";
import CampaignPage from "./CampaignPage";

export default function App() {
  const [authed, setAuthed] = useState(isLoggedIn());
  const [page, setPage] = useState("list"); // "list" | campaign id
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = () => setRefreshKey((k) => k + 1);

  function handleLogout() {
    clearApiKey();
    setAuthed(false);
    setPage("list");
  }

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />;
  }

  if (page !== "list") {
    return (
      <CampaignPage
        campaignId={page}
        onBack={() => setPage("list")}
        onLogout={handleLogout}
      />
    );
  }

  return (
    <main className="app">
      <header className="app__header">
        <h1 className="app__title">Automator</h1>
        <button className="btn btn--ghost" onClick={handleLogout}>Logout</button>
      </header>

      <section className="app__section">
        <Upload onUploaded={(id) => { refresh(); if (id) setPage(id); }} />
      </section>

      <section className="app__section">
        <CampaignList
          refreshKey={refreshKey}
          onSelect={(id) => setPage(id)}
          onRefresh={refresh}
        />
      </section>
    </main>
  );
}
