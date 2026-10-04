import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import QuestionView from "../components/QuestionView";
import { formatClock } from "../components/Timer";
import AssessmentPage, { isAnswered } from "../pages/Assessment";
import Review from "../pages/Review";
import { useAuth } from "../store";
import type { Question } from "../api";

const mcq: Question = {
  uid: "q1",
  kind: "mcq",
  number: 1,
  total: 2,
  points: 1,
  prompt: "Which is a stack?",
  options: [
    { id: "a", text: "Stack" },
    { id: "b", text: "Queue" },
  ],
};
const num: Question = {
  uid: "q2",
  kind: "numerical",
  number: 2,
  total: 2,
  points: 1,
  prompt: "What is 2 + 2?",
};

function wrap(ui: ReactNode, path = "/") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/assessment" element={ui} />
          <Route path="/review" element={ui} />
          <Route path="/submitted" element={<p>submitted page</p>} />
          <Route path="/" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

type Handler = (url: string, init?: RequestInit) => unknown;

function mockFetch(handler: Handler) {
  const calls: { url: string; body?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const data = handler(url, init);
      return new Response(JSON.stringify(data ?? {}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

const sessionInfo = {
  id: "s1",
  assessment: null,
  status: "in_progress",
  remaining_s: 600,
  total: 2,
  answered: 0,
  review_marks: [],
};

beforeEach(() => {
  sessionStorage.clear();
  useAuth.setState({ accessToken: "t", refreshToken: "r", username: "candidate", sessionId: "s1" });
});
afterEach(() => vi.unstubAllGlobals());

describe("helpers", () => {
  it("formats the clock", () => {
    expect(formatClock(65)).toBe("01:05");
    expect(formatClock(3661)).toBe("1:01:01");
    expect(formatClock(-3)).toBe("00:00");
  });

  it("detects answered responses", () => {
    expect(isAnswered(undefined)).toBe(false);
    expect(isAnswered({ option_id: "a" })).toBe(true);
    expect(isAnswered({ option_ids: [] })).toBe(false);
    expect(isAnswered({ value: "  " })).toBe(false);
    expect(isAnswered({ language: "python", code: "print(1)" })).toBe(true);
  });
});

describe("QuestionView", () => {
  it("reports the chosen option", async () => {
    const onChange = vi.fn();
    render(<QuestionView q={mcq} sessionId="s1" response={undefined} onChange={onChange} />);
    await userEvent.click(screen.getByLabelText("Queue"));
    expect(onChange).toHaveBeenCalledWith({ option_id: "b" });
  });

  it("renders tables", () => {
    const q: Question = { ...num, kind: "table", table: { columns: ["Name", "Score"], rows: [["Ana", 90]] } };
    render(<QuestionView q={q} sessionId="s1" response={undefined} onChange={() => {}} />);
    expect(screen.getByRole("columnheader", { name: "Score" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Ana" })).toBeInTheDocument();
  });
});

describe("Assessment page", () => {
  it("autosaves a choice and navigates between questions", async () => {
    const calls = mockFetch((url) => {
      if (url.endsWith("/sessions/s1")) return sessionInfo;
      if (url.endsWith("/questions")) return { questions: [mcq, num], responses: {} };
      if (url.endsWith("/answers")) return { saved: true };
    });
    wrap(<AssessmentPage />);
    expect(await screen.findByRole("heading", { name: /Question 1 of 2/ })).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Stack"));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/answers"))).toBe(true));
    expect(calls.find((c) => c.url.endsWith("/answers"))!.body).toEqual({
      question_uid: "q1",
      response: { option_id: "a" },
    });
    expect(await screen.findByText("All changes saved")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByRole("heading", { name: /Question 2 of 2/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review answers" })).toBeInTheDocument();
  });
});

describe("Review page", () => {
  it("confirms before submitting", async () => {
    const calls = mockFetch((url) => {
      if (url.endsWith("/sessions/s1")) return sessionInfo;
      if (url.endsWith("/questions"))
        return { questions: [mcq, num], responses: { q1: { response: { option_id: "a" } } } };
      if (url.endsWith("/submit")) return { status: "submitted" };
    });
    wrap(<Review />, "/review");
    expect(await screen.findByText(/1 answered · 1 unanswered/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Submit assessment" }));
    const dialog = screen.getByRole("dialog", { name: "Submit assessment?" });
    expect(dialog).toHaveTextContent("1 unanswered question");
    expect(calls.some((c) => c.url.endsWith("/submit"))).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("submitted page")).toBeInTheDocument();
    expect(calls.some((c) => c.url.endsWith("/submit"))).toBe(true);
  });
});
