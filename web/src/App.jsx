import { useState } from "react";
import Upload from "./Upload";
import CampaignList from "./CampaignList";
import LogViewer from "./LogViewer";

export default function App() {
  const [selected, setSelected] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = () => setRefreshKey((k) => k + 1);

  return (
    <main className="app">
      <header className="app__header">
        <h1 className="app__title">Automator</h1>
      </header>

      <section className="app__section">
        <Upload onUploaded={refresh} />
      </section>

      <section className="app__section">
        <CampaignList
          refreshKey={refreshKey}
          onSelect={setSelected}
          selected={selected}
          onRefresh={refresh}
        />
      </section>

      {selected && (
        <section className="app__section">
          <LogViewer campaignId={selected} />
        </section>
      )}
    </main>
  );
}
