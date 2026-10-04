import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { api, type Results } from "../api";
import { useAuth } from "../store";
import Layout from "../components/Layout";

const KIND_LABEL: Record<string, string> = {
  mcq: "Multiple choice",
  true_false: "True / false",
  multi_select: "Multi-select",
  numerical: "Numerical",
  text: "Short text",
  coding: "Coding",
  image: "Image",
  table: "Table",
};

export default function ResultsPage() {
  const sid = useAuth((s) => s.sessionId);
  const { data, error, isLoading } = useQuery({
    queryKey: ["results", sid],
    queryFn: () => api<Results>(`/sessions/${sid}/results`),
    enabled: !!sid,
  });
  if (!sid) return <Navigate to="/instructions" replace />;

  return (
    <Layout>
      {isLoading ? (
        <p>Loading results…</p>
      ) : error || !data ? (
        <p role="alert" className="text-rose-600">
          Results are not available yet.
        </p>
      ) : (
        <div className="mx-auto max-w-3xl space-y-6">
          <section className="rounded-lg bg-white p-6 shadow">
            <h1 className="text-xl font-semibold">Your results</h1>
            <p className="mt-2 text-3xl font-bold" data-testid="score">
              {data.score} / {data.max_score}
            </p>
            <p className="text-slate-600">
              {Math.round(data.accuracy * 100)}% of questions fully correct
              {data.status === "expired" && " · submitted automatically when time ran out"}
            </p>
          </section>

          <section className="rounded-lg bg-white p-6 shadow">
            <h2 className="mb-3 font-semibold">By question type</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th scope="col" className="py-1">
                    Type
                  </th>
                  <th scope="col">Correct</th>
                  <th scope="col">Points</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.by_kind).map(([k, v]) => (
                  <tr key={k} className="border-b border-slate-100">
                    <td className="py-1">{KIND_LABEL[k] ?? k}</td>
                    <td>
                      {v.correct} / {v.total}
                    </td>
                    <td>
                      {Math.round(v.points * 100) / 100} / {v.points_max}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="rounded-lg bg-white p-6 shadow">
            <h2 className="mb-3 font-semibold">By question</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th scope="col" className="py-1">
                    #
                  </th>
                  <th scope="col">Type</th>
                  <th scope="col">Result</th>
                  <th scope="col">Points</th>
                </tr>
              </thead>
              <tbody>
                {data.questions.map((q) => (
                  <tr key={q.number} className="border-b border-slate-100">
                    <td className="py-1">{q.number}</td>
                    <td>{KIND_LABEL[q.kind] ?? q.kind}</td>
                    <td
                      className={
                        q.error ? "text-amber-700" : q.correct ? "text-emerald-700" : "text-rose-700"
                      }
                      title={q.error}
                    >
                      {!q.answered
                        ? "Not answered"
                        : q.error
                          ? "Not graded (code judge unavailable)"
                          : q.correct
                            ? "Correct"
                            : "Incorrect"}
                      {q.tests_total !== undefined && ` (${q.tests_passed}/${q.tests_total} tests)`}
                    </td>
                    <td>
                      {q.points} / {q.points_max}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </Layout>
  );
}
