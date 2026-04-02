import { useState, useRef } from "react";
import { uploadCampaign } from "./api";

export default function Upload({ onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState(null);
  const inputRef = useRef();

  async function handle(file) {
    if (!file || !file.name.endsWith(".zip")) {
      setStatus({ type: "error", msg: ".zip 파일만 지원합니다" });
      return;
    }
    setStatus({ type: "loading", msg: "업로드 중..." });
    try {
      const res = await uploadCampaign(file);
      setStatus({ type: "success", msg: `업로드 완료 — ${res.id}` });
      onUploaded?.();
    } catch (e) {
      setStatus({ type: "error", msg: e.message });
    }
  }

  const zoneCls = `upload__zone${dragging ? " upload__zone--active" : ""}`;
  const statusCls = status ? `upload__status upload__status--${status.type}` : "";

  return (
    <div className="upload">
      <div
        className={zoneCls}
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handle(e.dataTransfer.files[0]); }}
      >
        캠페인 ZIP 파일을 드래그하거나 클릭하세요
        <input
          ref={inputRef}
          className="upload__input"
          type="file"
          accept=".zip"
          onChange={(e) => handle(e.target.files[0])}
        />
      </div>
      {status && <p className={statusCls}>{status.msg}</p>}
    </div>
  );
}
