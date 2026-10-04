import { useEffect, useRef, useState } from "react";

export function formatClock(s: number): string {
  const t = Math.max(0, Math.floor(s));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sec = t % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(sec).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Counts down from the server-provided remaining time; calls onExpire once at zero. */
export default function Timer({ remainingS, onExpire }: { remainingS: number; onExpire: () => void }) {
  const deadline = useRef(0); // set in the effect below (Date.now() is impure during render)
  const [left, setLeft] = useState(remainingS);
  const fired = useRef(false);

  useEffect(() => {
    deadline.current = Date.now() + remainingS * 1000;
  }, [remainingS]);

  useEffect(() => {
    const id = setInterval(() => {
      const l = (deadline.current - Date.now()) / 1000;
      setLeft(l);
      if (l <= 0 && !fired.current) {
        fired.current = true;
        onExpire();
      }
    }, 250);
    return () => clearInterval(id);
  }, [onExpire]);

  const urgent = left < 300;
  return (
    <div
      role="timer"
      aria-label="Time remaining"
      className={`rounded-md px-3 py-1 font-mono text-sm ${urgent ? "bg-rose-100 text-rose-700" : "bg-slate-100"}`}
    >
      Time remaining: {formatClock(left)}
    </div>
  );
}
