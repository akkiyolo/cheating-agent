import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";
import { api, ApiError, type Question, type Response, type SessionInfo } from "../api";
import { useAuth } from "../store";
import Layout, { Button } from "../components/Layout";
import Timer from "../components/Timer";
import QuestionView from "../components/QuestionView";

export const indexKey = (sid: string) => `qidx:${sid}`;

type SaveState = "idle" | "saving" | "saved" | "error";

interface QuestionsPayload {
  questions: Question[];
  responses: Record<string, { response: Response; revision: number }>;
}

export function isAnswered(r: Response | undefined): boolean {
  if (!r) return false;
  if ("option_id" in r) return !!r.option_id;
  if ("option_ids" in r) return r.option_ids.length > 0;
  if ("code" in r) return r.code.trim().length > 0;
  return r.value.trim().length > 0;
}

export default function AssessmentPage() {
  const sid = useAuth((s) => s.sessionId);
  if (!sid) return <Navigate to="/instructions" replace />;
  return <Assessment sid={sid} />;
}

function Assessment({ sid }: { sid: string }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const session = useQuery({
    queryKey: ["session", sid],
    queryFn: () => api<SessionInfo>(`/sessions/${sid}`),
  });
  const qs = useQuery({
    queryKey: ["questions", sid],
    queryFn: () => api<QuestionsPayload>(`/sessions/${sid}/questions`),
    enabled: session.data?.status === "in_progress",
  });

  const [index, setIndex] = useState(() => Number(sessionStorage.getItem(indexKey(sid)) ?? 0));
  // Local edits layered over the server copy; marks are overridden once the user toggles one.
  const [edits, setEdits] = useState<Record<string, Response>>({});
  const [marksOverride, setMarks] = useState<string[] | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const pending = useRef<Record<string, Response>>({});
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const serverResponses = useMemo(
    () => Object.fromEntries(Object.entries(qs.data?.responses ?? {}).map(([k, v]) => [k, v.response])),
    [qs.data],
  );
  const responses: Record<string, Response> = { ...serverResponses, ...edits };
  const marks = marksOverride ?? session.data?.review_marks ?? [];
  useEffect(() => {
    sessionStorage.setItem(indexKey(sid), String(index));
  }, [sid, index]);

  const save = useCallback(
    async (uid: string) => {
      const resp = pending.current[uid];
      if (!resp) return true;
      clearTimeout(timers.current[uid]);
      setSaveState("saving");
      try {
        await api(`/sessions/${sid}/answers`, {
          method: "POST",
          body: JSON.stringify({ question_uid: uid, response: resp }),
        });
        if (pending.current[uid] === resp) delete pending.current[uid];
        setSaveError(null);
        setSaveState(Object.keys(pending.current).length ? "saving" : "saved");
        return true;
      } catch (e) {
        setSaveState("error");
        setSaveError(e instanceof ApiError ? e.message : "Could not save your answer");
        return false;
      }
    },
    [sid],
  );

  const flushAll = useCallback(async () => {
    const results = await Promise.all(Object.keys(pending.current).map((uid) => save(uid)));
    return results.every(Boolean);
  }, [save]);

  // Save anything outstanding if the page is closed or the component unmounts.
  useEffect(() => {
    const t = timers.current;
    return () => {
      Object.values(t).forEach(clearTimeout);
      void flushAll();
    };
  }, [flushAll]);

  function onChange(q: Question, r: Response) {
    setEdits((prev) => ({ ...prev, [q.uid]: r }));
    pending.current[q.uid] = r;
    clearTimeout(timers.current[q.uid]);
    const immediate = q.kind === "mcq" || q.kind === "true_false" || q.kind === "multi_select";
    timers.current[q.uid] = setTimeout(() => void save(q.uid), immediate ? 0 : 700);
  }

  async function go(to: number) {
    await flushAll();
    setIndex(to);
    window.scrollTo(0, 0);
  }

  async function toReview() {
    await flushAll();
    qc.invalidateQueries({ queryKey: ["session", sid] });
    nav("/review");
  }

  async function toggleMark(uid: string) {
    const marked = !marks.includes(uid);
    const r = await api<{ review_marks: string[] }>(`/sessions/${sid}/review`, {
      method: "POST",
      body: JSON.stringify({ question_uid: uid, marked }),
    });
    setMarks(r.review_marks);
  }

  const onExpire = useCallback(async () => {
    await flushAll();
    try {
      await api(`/sessions/${sid}/submit`, { method: "POST" });
    } finally {
      nav("/submitted");
    }
  }, [flushAll, nav, sid]);

  if (session.isLoading || (session.data?.status === "in_progress" && qs.isLoading)) {
    return (
      <Layout>
        <p>Loading assessment…</p>
      </Layout>
    );
  }
  if (session.error || qs.error) {
    return (
      <Layout>
        <p role="alert" className="text-rose-600">
          Could not load the assessment. Please refresh the page.
        </p>
      </Layout>
    );
  }
  if (session.data && session.data.status !== "in_progress") return <Navigate to="/submitted" replace />;

  const questions = qs.data!.questions;
  const i = Math.min(Math.max(index, 0), questions.length - 1);
  const q = questions[i];
  const isLast = i === questions.length - 1;
  const marked = marks.includes(q.uid);

  return (
    <Layout right={<Timer remainingS={session.data!.remaining_s} onExpire={onExpire} />}>
      <div className="grid gap-6 lg:grid-cols-[12rem_1fr]">
        <nav aria-label="Question navigator" className="space-y-2">
          <div className="text-sm text-slate-500">
            {questions.filter((x) => isAnswered(responses[x.uid])).length} of {questions.length} answered
          </div>
          <ol className="grid grid-cols-5 gap-1 lg:grid-cols-4">
            {questions.map((x, n) => {
              const done = isAnswered(responses[x.uid]);
              const flag = marks.includes(x.uid);
              return (
                <li key={x.uid}>
                  <button
                    aria-label={`Question ${n + 1}${done ? ", answered" : ""}${flag ? ", marked for review" : ""}`}
                    aria-current={n === i ? "step" : undefined}
                    onClick={() => void go(n)}
                    className={`relative h-9 w-full rounded text-sm ${
                      n === i ? "ring-2 ring-indigo-500" : ""
                    } ${done ? "bg-indigo-600 text-white" : "border border-slate-300 bg-white"}`}
                  >
                    {n + 1}
                    {flag && (
                      <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-amber-400" />
                    )}
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        <section aria-labelledby="q-heading" className="space-y-5 rounded-lg bg-white p-6 shadow">
          <div className="flex items-center justify-between gap-4">
            <h1 id="q-heading" className="text-lg font-semibold">
              Question {i + 1} of {questions.length}
              <span className="ml-2 text-sm font-normal text-slate-500">
                ({q.points} {q.points === 1 ? "point" : "points"})
              </span>
            </h1>
            <span role="status" aria-live="polite" className="text-sm text-slate-500">
              {{ idle: "", saving: "Saving…", saved: "All changes saved", error: "Not saved" }[saveState]}
            </span>
          </div>

          {saveError && (
            <div
              role="alert"
              className="flex items-center justify-between rounded bg-rose-50 px-3 py-2 text-sm text-rose-700"
            >
              <span>Your last answer was not saved: {saveError}</span>
              <Button variant="secondary" onClick={() => void flushAll()}>
                Retry
              </Button>
            </div>
          )}

          <QuestionView
            key={q.uid}
            q={q}
            sessionId={sid}
            response={responses[q.uid]}
            onChange={(r) => onChange(q, r)}
          />

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
            <Button variant="secondary" disabled={i === 0} onClick={() => void go(i - 1)}>
              Previous
            </Button>
            <Button variant="secondary" aria-pressed={marked} onClick={() => void toggleMark(q.uid)}>
              {marked ? "Unmark review" : "Mark for review"}
            </Button>
            {isLast ? (
              <Button onClick={() => void toReview()}>Review answers</Button>
            ) : (
              <Button onClick={() => void go(i + 1)}>Next</Button>
            )}
          </div>
        </section>
      </div>
    </Layout>
  );
}
