import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  doctor: "Doctor",
  nurse: "Nurse",
  researcher: "Researcher",
};

function NavLink({ to, children }: { to: string; children: ReactNode }) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link
      to={to}
      className={`flex items-center rounded-lg px-3 py-2 text-sm font-medium transition ${
        isActive ? "bg-primary-soft text-primary-dark" : "text-ink-muted hover:bg-bg"
      }`}
    >
      {children}
    </Link>
  );
}

export function AppLayout({ children, title }: { children: ReactNode; title: string }) {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen bg-bg">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-border bg-surface">
        <div className="flex h-16 items-center gap-2 border-b border-border px-5">
          <svg width="24" height="18" viewBox="0 0 28 20" fill="none">
            <path
              d="M0 10H6L8.5 3L13 17L16 10H28"
              stroke="var(--color-primary)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="text-sm font-semibold text-ink">MedIntel AI</span>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          <NavLink to="/dashboard">Executive Overview</NavLink>
          <NavLink to="/icu-risk">ICU Risk Check</NavLink>
          <NavLink to="/patients">Patients</NavLink>
          <NavLink to="/glucotwin">GlucoTwin (T2D)</NavLink>
          <div className="flex items-center rounded-lg px-3 py-2 text-sm text-ink-muted/60">
            Disease Analytics
            <span className="ml-auto rounded-full bg-bg px-1.5 py-0.5 text-[10px]">Sprint 4</span>
          </div>
        </nav>
      </aside>

      {/* Main column */}
      <div className="flex flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-border bg-surface px-6">
          <h1 className="text-lg font-semibold text-ink">{title}</h1>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-sm font-medium text-ink">{user?.full_name}</div>
              <div className="text-xs text-ink-muted">
                {user ? ROLE_LABELS[user.role] ?? user.role : ""}
              </div>
            </div>
            <button
              onClick={logout}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-ink-muted transition hover:bg-bg"
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
