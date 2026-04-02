import { useState } from "react";
import { verifyApiKey, setApiKey } from "./api";

export default function Login({ onLogin }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!key.trim()) return;

    setLoading(true);
    setError("");

    try {
      const ok = await verifyApiKey(key.trim());
      if (ok) {
        setApiKey(key.trim());
        onLogin();
      } else {
        setError("API key가 올바르지 않습니다");
      }
    } catch {
      setError("서버에 연결할 수 없습니다");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login">
      <form className="login__card" onSubmit={handleSubmit}>
        <h1 className="login__title">Automator</h1>
        <label className="login__label" htmlFor="api-key">API Key</label>
        <input
          id="api-key"
          className="login__input"
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="API key를 입력하세요"
          autoFocus
        />
        {error && <p className="login__error">{error}</p>}
        <button className="login__submit" type="submit" disabled={loading}>
          {loading ? "확인 중..." : "로그인"}
        </button>
      </form>
    </main>
  );
}
