import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../store";

export default function Layout({ children, right }: { children: ReactNode; right?: ReactNode }) {
  const { username, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <span className="font-semibold text-slate-800">Online Assessment</span>
          <div className="flex items-center gap-4 text-sm">
            {right}
            {username && (
              <>
                <span className="text-slate-500">{username}</span>
                <button
                  className="text-slate-500 underline hover:text-slate-800"
                  onClick={() => {
                    logout();
                    nav("/login");
                  }}
                >
                  Sign out
                </button>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const styles = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300",
    secondary: "border border-slate-300 bg-white text-slate-800 hover:bg-slate-100 disabled:text-slate-400",
    danger: "bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300",
  }[variant];
  return (
    <button
      className={`rounded-md px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${styles} ${className}`}
      {...props}
    />
  );
}
