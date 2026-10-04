import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type Assessment } from "../api";
import { useAuth } from "../store";
import Layout, { Button } from "../components/Layout";

export default function Instructions() {
  const nav = useNavigate();
  const setSession = useAuth((s) => s.setSession);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["assessments"],
    queryFn: () => api<Assessment[]>("/assessments"),
  });
  const a = data?.[0];

  async function start() {
    if (!a) return;
    try {
      const r = await api<{ session_id: string }>(`/assessments/${a.id}/start`, { method: "POST" });
      setSession(r.session_id);
      nav("/assessment");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start");
    }
  }

  return (
    <Layout>
      {isLoading || !a ? (
        <p>Loading…</p>
      ) : (
        <article className="mx-auto max-w-2xl space-y-4 rounded-lg bg-white p-6 shadow">
          <h1 className="text-2xl font-semibold">{a.title}</h1>
          <p className="text-slate-600">{a.description}</p>
          <h2 className="font-semibold">Instructions</h2>
          <ul className="list-disc space-y-1 pl-6 text-sm text-slate-700">
            <li>
              You have <strong>{Math.round(a.duration_s / 60)} minutes</strong> to answer {a.question_count}{" "}
              questions. The timer starts when you begin and cannot be paused.
            </li>
            <li>Answers are saved automatically. You can move between questions freely.</li>
            <li>Use “Mark for review” to flag questions you want to revisit.</li>
            <li>Coding questions can be run against the sample tests before submitting.</li>
            <li>The assessment is submitted automatically when time runs out.</li>
          </ul>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />I have
            read the instructions
          </label>
          {error && (
            <p role="alert" className="text-sm text-rose-600">
              {error}
            </p>
          )}
          <Button disabled={!agreed} onClick={start}>
            Start assessment
          </Button>
        </article>
      )}
    </Layout>
  );
}
