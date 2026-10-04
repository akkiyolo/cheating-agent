import { useAuth } from "./store";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const BASE = "/api";

async function refreshTokens(): Promise<boolean> {
  const { refreshToken, setTokens, logout } = useAuth.getState();
  if (!refreshToken) return false;
  const r = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!r.ok) {
    logout();
    return false;
  }
  const t = await r.json();
  setTokens(t.access_token, t.refresh_token, t.username);
  return true;
}

export async function api<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const token = useAuth.getState().accessToken;
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const r = await fetch(`${BASE}${path}`, { ...init, headers });
  if (r.status === 401 && !retried && (await refreshTokens())) return api<T>(path, init, true);
  if (!r.ok) {
    let msg = r.statusText;
    try {
      msg = (await r.json()).detail ?? msg;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(r.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return r.json() as Promise<T>;
}

export async function fetchImage(path: string): Promise<string> {
  const token = useAuth.getState().accessToken;
  const r = await fetch(`${BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!r.ok) throw new ApiError(r.status, "image failed to load");
  return URL.createObjectURL(await r.blob());
}

// ---- types --------------------------------------------------------------------------------

export type Kind = "mcq" | "true_false" | "multi_select" | "numerical" | "text" | "coding" | "image" | "table";

export interface Option {
  id: string;
  text: string;
}

export interface Coding {
  title: string;
  statement: string;
  input_format: string;
  output_format: string;
  examples: { input: string; output: string }[];
  languages: string[];
}

export interface Question {
  uid: string;
  kind: Kind;
  number: number;
  total: number;
  points: number;
  prompt: string;
  code?: string;
  passage?: string;
  options?: Option[];
  table?: { columns: string[]; rows: (string | number)[][] };
  image?: { alt: string };
  coding?: Coding;
}

export type Response =
  | { option_id: string }
  | { option_ids: string[] }
  | { value: string }
  | { language: string; code: string };

export interface SessionInfo {
  id: string;
  assessment: { id: string; title: string } | null;
  status: "in_progress" | "submitted" | "expired" | "abandoned";
  remaining_s: number;
  total: number;
  answered: number;
  review_marks: string[];
}

export interface Assessment {
  id: string;
  slug: string;
  title: string;
  description: string;
  duration_s: number;
  question_count: number;
}

export interface RunResult {
  compiled: boolean;
  compile_error: string | null;
  passed: boolean;
  tests_passed: number;
  tests_failed: number;
  execution_time_ms: number;
  error: string | null;
  cases: { index: number; passed: boolean | null; stdout: string; stderr: string; expected: string | null;
    timed_out: boolean; exit_code: number }[];
}

export interface Results {
  status: string;
  score: number;
  max_score: number;
  accuracy: number;
  by_kind: Record<string, { correct: number; total: number; points: number; points_max: number }>;
  questions: { number: number; kind: string; answered: boolean; correct: boolean; points: number;
    points_max: number; tests_passed?: number; tests_total?: number }[];
}
