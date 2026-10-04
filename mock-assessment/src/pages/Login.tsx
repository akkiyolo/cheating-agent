import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../store";
import Layout, { Button } from "../components/Layout";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const setTokens = useAuth((s) => s.setTokens);
  const nav = useNavigate();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const t = await api<{ access_token: string; refresh_token: string; username: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setTokens(t.access_token, t.refresh_token, t.username);
      nav("/instructions");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout>
      <form onSubmit={onSubmit} className="mx-auto mt-16 max-w-sm space-y-4 rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold">Sign in</h1>
        <label className="block text-sm">
          Username
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label className="block text-sm">
          Password
          <input
            type="password"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-rose-600">
            {error}
          </p>
        )}
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </Layout>
  );
}
