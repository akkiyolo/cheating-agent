import { useEffect, useState } from "react";
import { api, ApiError, fetchImage, type Question, type Response, type RunResult } from "../api";
import { Button } from "./Layout";

export const STARTERS: Record<string, string> = {
  python:
    "import sys\n\ndef main():\n    data = sys.stdin.read().split()\n    # your solution here\n\nmain()\n",
  cpp: "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    // your solution here\n    return 0;\n}\n",
  java: "import java.util.*;\nimport java.io.*;\n\npublic class Main {\n    public static void main(String[] args) throws IOException {\n        // your solution here\n    }\n}\n",
};

function QuestionImage({ sessionId, uid }: { sessionId: string; uid: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    fetchImage(`/sessions/${sessionId}/questions/${uid}/image.png`)
      .then((u) => {
        url = u;
        setSrc(u);
      })
      .catch(() => setErr(true));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [sessionId, uid]);
  if (err) return <p role="alert">Image failed to load.</p>;
  return src ? (
    <img src={src} alt="Question figure" className="max-w-full rounded border border-slate-200" />
  ) : (
    <p>Loading image…</p>
  );
}

function CodeQuestion({
  q,
  sessionId,
  value,
  onChange,
}: {
  q: Question;
  sessionId: string;
  value: { language: string; code: string } | undefined;
  onChange: (r: Response) => void;
}) {
  const c = q.coding!;
  const language = value?.language ?? "python";
  const code = value?.code ?? STARTERS[language];
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setRunError(null);
    try {
      setResult(
        await api<RunResult>("/code/run", {
          method: "POST",
          body: JSON.stringify({ language, code, session_id: sessionId, question_uid: q.uid }),
        }),
      );
    } catch (e) {
      setRunError(e instanceof ApiError ? e.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2 text-sm">
        <p className="whitespace-pre-wrap">{c.statement}</p>
        <h3 className="font-semibold">Input</h3>
        <p className="whitespace-pre-wrap">{c.input_format}</p>
        <h3 className="font-semibold">Output</h3>
        <p className="whitespace-pre-wrap">{c.output_format}</p>
        <h3 className="font-semibold">Examples</h3>
        {c.examples.map((ex, i) => (
          <div key={i} className="grid grid-cols-2 gap-2" data-testid="example">
            <div>
              <div className="text-xs text-slate-500">Sample input {i + 1}</div>
              <pre className="rounded bg-slate-100 p-2 font-mono text-xs">{ex.input}</pre>
            </div>
            <div>
              <div className="text-xs text-slate-500">Sample output {i + 1}</div>
              <pre className="rounded bg-slate-100 p-2 font-mono text-xs">{ex.output}</pre>
            </div>
          </div>
        ))}
      </div>
      <label className="block text-sm">
        Language
        <select
          className="ml-2 rounded border border-slate-300 px-2 py-1"
          value={language}
          onChange={(e) => {
            const lang = e.target.value;
            const isStarter = Object.values(STARTERS).includes(code);
            onChange({ language: lang, code: isStarter ? STARTERS[lang] : code });
          }}
        >
          {c.languages.map((l) => (
            <option key={l} value={l}>
              {{ python: "Python 3", cpp: "C++17", java: "Java 21" }[l] ?? l}
            </option>
          ))}
        </select>
      </label>
      <textarea
        aria-label="Code editor"
        spellCheck={false}
        className="h-80 w-full rounded border border-slate-300 bg-slate-900 p-3 font-mono text-sm text-slate-100"
        value={code}
        onChange={(e) => onChange({ language, code: e.target.value })}
      />
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={run} disabled={running}>
          {running ? "Running…" : "Run sample tests"}
        </Button>
        {runError && (
          <span role="alert" className="text-sm text-rose-600">
            {runError}
          </span>
        )}
      </div>
      {result && (
        <section aria-label="Run results" className="rounded border border-slate-200 p-3 text-sm">
          {!result.compiled ? (
            <>
              <p className="font-semibold text-rose-700">Compilation error</p>
              <pre className="whitespace-pre-wrap font-mono text-xs">{result.compile_error}</pre>
            </>
          ) : (
            <>
              <p className={result.passed ? "font-semibold text-emerald-700" : "font-semibold text-rose-700"}>
                Sample tests passed: {result.tests_passed}/{result.tests_passed + result.tests_failed}
              </p>
              <ul className="mt-2 space-y-1">
                {result.cases.map((cs) => (
                  <li key={cs.index}>
                    Test {cs.index + 1}:{" "}
                    {cs.passed ? "passed" : cs.timed_out ? "time limit exceeded" : "failed"}
                    {!cs.passed && (
                      <pre className="whitespace-pre-wrap font-mono text-xs text-slate-600">
                        {`stdout: ${cs.stdout.slice(0, 500)}\nstderr: ${cs.stderr.slice(0, 500)}`}
                      </pre>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </div>
  );
}

export default function QuestionView({
  q,
  sessionId,
  response,
  onChange,
}: {
  q: Question;
  sessionId: string;
  response: Response | undefined;
  onChange: (r: Response) => void;
}) {
  const r = response as Record<string, unknown> | undefined;
  return (
    <div className="space-y-4">
      <p className="whitespace-pre-wrap text-base" data-testid="question-prompt">
        {q.kind === "coding" ? q.coding?.title : q.prompt}
      </p>
      {q.passage && (
        <blockquote aria-label="Passage" className="border-l-4 border-slate-300 pl-3 text-slate-700">
          {q.passage}
        </blockquote>
      )}
      {q.code && (
        <pre
          aria-label="Code snippet"
          className="overflow-x-auto rounded bg-slate-900 p-3 font-mono text-sm text-slate-100"
        >
          {q.code}
        </pre>
      )}
      {q.table && (
        <table className="min-w-[24rem] border-collapse text-sm">
          <thead>
            <tr>
              {q.table.columns.map((c) => (
                <th key={c} scope="col" className="border border-slate-300 bg-slate-100 px-3 py-1 text-left">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {q.table.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j} className="border border-slate-300 px-3 py-1">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {q.image && <QuestionImage sessionId={sessionId} uid={q.uid} />}

      {(q.kind === "mcq" || q.kind === "true_false") && (
        <fieldset className="space-y-2">
          <legend className="sr-only">Choose one answer</legend>
          {q.options!.map((o) => (
            <label
              key={o.id}
              className="flex cursor-pointer items-center gap-3 rounded border border-slate-200 bg-white px-3 py-2 hover:bg-slate-50"
            >
              <input
                type="radio"
                name={`q-${q.uid}`}
                value={o.id}
                checked={r?.option_id === o.id}
                onChange={() => onChange({ option_id: o.id })}
              />
              <span>{o.text}</span>
            </label>
          ))}
        </fieldset>
      )}

      {q.kind === "multi_select" && (
        <fieldset className="space-y-2">
          <legend className="text-sm text-slate-500">Select all that apply</legend>
          {q.options!.map((o) => {
            const chosen = (r?.option_ids as string[] | undefined) ?? [];
            return (
              <label
                key={o.id}
                className="flex cursor-pointer items-center gap-3 rounded border border-slate-200 bg-white px-3 py-2 hover:bg-slate-50"
              >
                <input
                  type="checkbox"
                  value={o.id}
                  checked={chosen.includes(o.id)}
                  onChange={(e) =>
                    onChange({
                      option_ids: e.target.checked ? [...chosen, o.id] : chosen.filter((x) => x !== o.id),
                    })
                  }
                />
                <span>{o.text}</span>
              </label>
            );
          })}
        </fieldset>
      )}

      {(q.kind === "numerical" || q.kind === "image" || q.kind === "table") && (
        <label className="block text-sm">
          Your answer
          <input
            inputMode="decimal"
            className="mt-1 block w-64 rounded border border-slate-300 px-3 py-2"
            value={(r?.value as string | undefined) ?? ""}
            onChange={(e) => onChange({ value: e.target.value })}
          />
        </label>
      )}

      {q.kind === "text" && (
        <label className="block text-sm">
          Your answer
          <input
            className="mt-1 block w-96 rounded border border-slate-300 px-3 py-2"
            value={(r?.value as string | undefined) ?? ""}
            onChange={(e) => onChange({ value: e.target.value })}
          />
        </label>
      )}

      {q.kind === "coding" && (
        <CodeQuestion
          q={q}
          sessionId={sessionId}
          value={response as { language: string; code: string } | undefined}
          onChange={onChange}
        />
      )}
    </div>
  );
}
