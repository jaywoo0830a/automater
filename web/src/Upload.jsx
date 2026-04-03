import { useState, useRef } from "react";
import { uploadCampaign } from "./api";

export default function Upload({ onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState(null);
  const [file, setFile] = useState(null);
  const [name, setName] = useState("");
  const inputRef = useRef();

  function handleFile(f) {
    if (!f || !f.name.endsWith(".zip")) {
      setStatus({ type: "error", msg: ".zip only" });
      return;
    }
    setFile(f);
    setName(f.name.replace(".zip", ""));
    setStatus(null);
  }

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) return;
    setStatus({ type: "loading", msg: "Uploading..." });
    try {
      const res = await uploadCampaign(file, name);
      setStatus({ type: "success", msg: `Uploaded — ${name || res.id}` });
      setFile(null);
      setName("");
      onUploaded?.(res.id);
    } catch (err) {
      setStatus({ type: "error", msg: err.message });
    }
  }

  const zoneCls = `upload__zone${dragging ? " upload__zone--active" : ""}`;
  const statusCls = status ? `upload__status upload__status--${status.type}` : "";

  return (
    <div className="upload">
      {!file ? (
        <div
          className={zoneCls}
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
        >
          Drop ZIP or click to select
          <input
            ref={inputRef}
            className="upload__input"
            type="file"
            accept=".zip"
            onChange={(e) => handleFile(e.target.files[0])}
          />
        </div>
      ) : (
        <form className="upload__form" onSubmit={handleUpload}>
          <div className="upload__file-info">
            <code>{file.name}</code>
            <button type="button" className="btn btn--ghost" onClick={() => { setFile(null); setName(""); }}>
              cancel
            </button>
          </div>
          <input
            className="upload__name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Campaign name"
            autoFocus
          />
          <button className="upload__submit" type="submit">Upload</button>
        </form>
      )}
      {status && <p className={statusCls}>{status.msg}</p>}
    </div>
  );
}
