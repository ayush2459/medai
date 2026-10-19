import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  doctor: "Doctor",
  nurse: "Nurse",
  researcher: "Researcher",
};

const NAV = [
  { to: "/dashboard", label: "Overview", section: "WORKSPACE", icon: "grid" },
  { to: "/patients", label: "Patients", icon: "users" },
  { to: "/icu-risk", label: "ICU Risk Monitor", icon: "activity" },
  { to: "/glucotwin", label: "GlucoTwin", section: "DIGITAL TWIN", icon: "activity" },
  { to: "/analytics", label: "Disease Analytics", section: "INTELLIGENCE", icon: "chart" },
  { to: "/reports", label: "Reports", section: "OPERATIONS", icon: "chart" },
];

function NavIcon({ name }: { name: string }) {
  const common = {
    width: 19,
    height: 19,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };

  switch (name) {
    case "grid":
      return (
        <svg {...common}>
          <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
          <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
          <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
          <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "users":
      return (
        <svg {...common}>
          <path d="M16 20v-1.5a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V20" />
          <circle cx="9.5" cy="7.5" r="3.5" />
          <path d="M17 4.5a3.5 3.5 0 0 1 0 6.8M21 20v-1.5a4 4 0 0 0-3-3.87" />
        </svg>
      );
    case "activity":
      return (
        <svg {...common}>
          <path d="M3 12h4l3-8 4 16 3-8h4" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <path d="M4 19V5M4 19h17" />
          <path d="m7 15 4-4 3 2 6-7" />
        </svg>
      );
  }
}

export function AppLayout({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  const { user, logout } = useAuth();
  const location = useLocation();

  const initials =
    user?.full_name
      ?.trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "MI";

  const today = new Date().toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="min-h-screen bg-[#f5f8fb] text-slate-800 lg:flex">
      {/* Desktop sidebar */}
      <aside className="hidden w-[258px] shrink-0 flex-col border-r border-slate-200/80 bg-white px-5 py-6 lg:sticky lg:top-0 lg:flex lg:h-screen">
        <Link to="/dashboard" className="mb-9 flex items-center gap-3 px-1 no-underline">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#0d5962] text-white shadow-sm shadow-teal-900/15">
            <svg
              width="27"
              height="27"
              viewBox="0 0 32 32"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M4 16h6l3-8 6 17 4-10h5"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span className="flex flex-col">
            <strong className="text-[20px] font-extrabold tracking-[-0.8px] text-slate-900">
              MedIntel <span className="text-[#0d8790]">AI</span>
            </strong>
            <span className="mt-0.5 text-[9px] font-bold tracking-[2px] text-slate-400">
              CLINICAL INTELLIGENCE
            </span>
          </span>
        </Link>

        <div className="mb-7 flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-50 text-[#0d7379]">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M3 21h18M5 21V7l7-4 7 4v14M9 10h.01M15 10h.01M9 14h.01M15 14h.01M10 21v-4h4v4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="min-w-0 flex-1">
            <strong className="block text-xs font-bold text-slate-800">Hospital workspace</strong>
            <span className="mt-1 block text-[11px] text-slate-500">Clinical operations</span>
          </span>
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
        </div>

        <nav className="flex-1 space-y-6" aria-label="Main navigation">
          {NAV.map((item) => {
            const active = location.pathname === item.to;

            return (
              <div key={item.to}>
                {item.section && (
                  <p className="mb-2 px-3 text-[10px] font-extrabold tracking-[1.7px] text-slate-400">
                    {item.section}
                  </p>
                )}
                <Link
                  to={item.to}
                  aria-current={active ? "page" : undefined}
                  className={`group mb-1 flex min-h-11 items-center gap-3 rounded-xl px-3 text-[13px] font-semibold no-underline transition-colors ${
                    active
                      ? "bg-[#e8f5f4] text-[#087078]"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <span className={active ? "text-[#087078]" : "text-slate-400 group-hover:text-slate-600"}>
                    <NavIcon name={item.icon} />
                  </span>
                  <span className="flex-1">{item.label}</span>
                  {item.to === "/icu-risk" && (
                    <span className="rounded-md bg-rose-50 px-1.5 py-1 text-[9px] font-extrabold tracking-wide text-rose-600">
                      LIVE
                    </span>
                  )}
                  {active && <span className="h-1.5 w-1.5 rounded-full bg-[#0d8790]" />}
                </Link>
              </div>
            );
          })}
        </nav>

        <div className="mt-7 rounded-2xl border border-teal-100 bg-gradient-to-br from-teal-50 to-white p-4">
          <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-white text-[#0d7379] shadow-sm">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
              <circle cx="12" cy="12" r="9" />
              <path d="M9.6 9a2.5 2.5 0 0 1 4.8 1c0 1.7-2.4 2-2.4 3.8M12 17.2h.01" strokeLinecap="round" />
            </svg>
          </div>
          <p className="text-sm font-bold text-slate-800">Clinical workspace</p>
          <p className="mt-1.5 text-xs leading-5 text-slate-500">
            Review patient information and decision-support insights.
          </p>
          <p className="mt-3 text-[10px] leading-4 text-slate-400">
            Use clinical judgement when interpreting model outputs.
          </p>
        </div>

        <div className="mt-5 flex items-center gap-2.5 border-t border-slate-100 px-1 pt-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M12 3 20 6v5c0 5-3.4 8.2-8 10-4.6-1.8-8-5-8-10V6l8-3Z" />
              <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="flex-1">
            <strong className="block text-[11px] font-bold text-slate-700">Secure environment</strong>
            <span className="mt-0.5 block text-[10px] text-slate-400">Session protected</span>
          </span>
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
        </div>
      </aside>

      {/* Main content */}
      <div className="min-w-0 flex-1">
        {/* Mobile brand and navigation */}
        <div className="border-b border-slate-200 bg-white px-4 py-4 lg:hidden">
          <div className="flex items-center justify-between gap-3">
            <Link to="/dashboard" className="flex items-center gap-2.5 no-underline">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#0d5962] text-white">
                <svg width="23" height="23" viewBox="0 0 32 32" fill="none" aria-hidden="true">
                  <path d="M4 16h6l3-8 6 17 4-10h5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <span className="text-lg font-extrabold tracking-tight text-slate-900">
                MedIntel <span className="text-[#0d8790]">AI</span>
              </span>
            </Link>
            <button
              onClick={logout}
              className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600"
            >
              Sign out
            </button>
          </div>
          <nav className="mt-4 flex gap-2 overflow-x-auto pb-1" aria-label="Mobile navigation">
            {NAV.map((item) => {
              const active = location.pathname === item.to;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  aria-current={active ? "page" : undefined}
                  className={`shrink-0 rounded-lg px-3 py-2 text-xs font-semibold no-underline ${
                    active
                      ? "bg-[#e8f5f4] text-[#087078]"
                      : "bg-slate-50 text-slate-600"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Top bar */}
        <header className="sticky top-0 z-20 hidden h-[74px] items-center justify-between border-b border-slate-200/80 bg-white/95 px-7 backdrop-blur-xl md:flex xl:px-10">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <span className="text-slate-400">Workspace</span>
            <span className="text-slate-300">/</span>
            <span className="truncate font-semibold text-slate-800">{title}</span>
          </div>

          <div className="flex items-center gap-5">
            <div className="flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50/70 px-3 py-2">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              <span className="text-[11px] font-semibold text-emerald-800">Workspace active</span>
            </div>

            <div className="h-8 w-px bg-slate-200" />

            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-full border border-teal-100 bg-[#e8f5f4] text-xs font-extrabold text-[#087078]">
                {initials}
              </span>
              <span className="max-w-[175px]">
                <strong className="block truncate text-xs font-bold text-slate-800">
                  {user?.full_name || "Clinical user"}
                </strong>
                <span className="mt-1 block text-[10px] font-medium text-slate-500">
                  {user ? ROLE_LABELS[user.role] ?? user.role : "Team member"}
                </span>
              </span>
              <button
                onClick={logout}
                className="ml-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
                title="Sign out"
                aria-label="Sign out"
              >
                Sign out
              </button>
            </div>
          </div>
        </header>

        <main className="mx-auto min-h-[calc(100vh-74px)] w-full max-w-[1700px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8 xl:px-10">
          <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="mb-2 flex items-center gap-2 text-[10px] font-extrabold tracking-[1.8px] text-[#0d8790]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#0d8790]" />
                MEDINTEL AI
                <span className="text-slate-300">/</span>
                <span className="text-slate-400">CLINICAL WORKSPACE</span>
              </div>
              <h1 className="text-2xl font-extrabold tracking-[-0.8px] text-slate-900 sm:text-[30px]">
                {title}
              </h1>
              <p className="mt-1.5 text-xs text-slate-500">
                Clinical insights and operational overview
              </p>
            </div>

            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 shadow-sm shadow-slate-900/[0.02]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
                <rect x="3.5" y="5" width="17" height="15" rx="2" />
                <path d="M7.5 3.5v3M16.5 3.5v3M3.5 9.5h17" strokeLinecap="round" />
              </svg>
              <span className="text-xs font-semibold text-slate-600">{today}</span>
            </div>
          </div>

          {children}

          <footer className="mt-10 flex flex-col gap-2 border-t border-slate-200/80 py-5 text-[10px] leading-5 text-slate-400 sm:flex-row sm:items-center sm:justify-between">
            <span>© 2026 MedIntel AI</span>
            <span>Designed for better-informed care</span>
            <span className="max-w-xl sm:text-right">
              Clinical decision support only · Not a substitute for professional clinical judgement
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
