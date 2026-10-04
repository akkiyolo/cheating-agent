import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";
import { api, ApiError, type Question, type Response, type SessionInfo } from "../api";
import { useAuth } from "../store";
import Layout, { Button } from "../components/Layout";
import Timer from "../components/Timer";
import { indexKey, isAnswered } from "./Assessment";

export default function Review() {
  const sid = useAuth((s) => s.sessionId);
  const nav = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const session = useQuery({
    queryKey: ["session", sid],
    queryFn: () => api<SessionInfo>(`/sessions/${sid}`),
    enabled: !!sid,
  });
  const qs = useQuery({
    queryKey: ["questions", sid, "review"],
    queryFn: () =>
      api<{ questions: Question[]; responses: Record<string, { response: Response }> }>(
        `/sessions/${sid}/questions`,
      ),
    enabled: !!sid && session.data?.status === "in_progress",
  });

  if (!sid) return <Navigate to="/instructions" replace />;
  if (session.data && session.data.status !== "in_progress") return <Navigate to="/submitted" replace />;

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      await api(`/sessions/${sid}/submit`, { method: "POST" });
      nav("/submitted");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Submission failed, please try again");
      setSubmitting(false);
    }
  }

  function open(n: number) {
    sessionStorage.setItem(indexKey(sid!), String(n));
    nav("/assessment");
  }

  if (!session.data || !qs.data) {
    return (
      <Layout>
        <p>Loading…</p>
      </Layout>
    );
  }

  const { questions, responses } = qs.data;
  const marks = session.data.review_marks;
  const unanswered = questions.filter((q) => !isAnswered(responses[q.uid]?.response)).length;

  return (
    <Layout right={<Timer remainingS={session.data.remaining_s} onExpire={() => void submit()} />}>
      <div className="mx-auto max-w-3xl space-y-4 rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold">Review your answers</h1>
        <p className="text-sm text-slate-600">
          {questions.length - unanswered} answered · {unanswered} unanswered · {marks.length} marked for
          review
        </p>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th scope="col" className="py-2">
                Question
              </th>
              <th scope="col">Status</th>
              <th scope="col">
                <span className="sr-only">Action</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {questions.map((q, n) => {
              const done = isAnswered(responses[q.uid]?.response);
              const flag = marks.includes(q.uid);
              const title = q.kind === "coding" ? q.coding?.title : q.prompt;
              return (
                <tr key={q.uid} className="border-b border-slate-100">
                  <td className="py-2 pr-4">
                    <span className="font-medium">{n + 1}.</span>{" "}
                    <span className="text-slate-700">
                      {title && title.length > 70 ? `${title.slice(0, 70)}…` : title}
                    </span>
                  </td>
                  <td className="whitespace-nowrap pr-4">
                    <span className={done ? "text-emerald-700" : "text-rose-700"}>
                      {done ? "Answered" : "Not answered"}
                    </span>
                    {flag && <span className="ml-2 rounded bg-amber-100 px-1.5 text-amber-800">Marked</span>}
                  </td>
                  <td className="text-right">
                    <button className="text-indigo-700 underline" onClick={() => open(n)}>
                      Go to question {n + 1}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {error && (
          <p role="alert" className="text-sm text-rose-600">
            {error}
          </p>
        )}
        <div className="flex justify-between">
          <Button variant="secondary" onClick={() => open(0)}>
            Back to questions
          </Button>
          <Button onClick={() => setConfirming(true)}>Submit assessment</Button>
        </div>
      </div>

      {confirming && (
        <div className="fixed inset-0 flex items-center justify-center bg-slate-900/40">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            className="w-96 space-y-4 rounded-lg bg-white p-6 shadow-xl"
          >
            <h2 id="confirm-title" className="text-lg font-semibold">
              Submit assessment?
            </h2>
            <p className="text-sm text-slate-600">
              {unanswered > 0
                ? `You have ${unanswered} unanswered question${unanswered === 1 ? "" : "s"}. `
                : "All questions are answered. "}
              You cannot change your answers after submitting.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirming(false)} disabled={submitting}>
                Cancel
              </Button>
              <Button onClick={() => void submit()} disabled={submitting}>
                {submitting ? "Submitting…" : "Submit"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
