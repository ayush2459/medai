import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppLayout } from "../components/AppLayout";
import { KpiCard } from "../components/KpiCard";
import { api } from "../lib/api";
import type { ExecutiveSummary } from "../lib/types";

function formatDay(iso: string): string {
  const date = new Date(iso);

  if (Number.isNaN(date.getTime())) {
    return iso;
  }

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

const tooltipStyle = {
  backgroundColor: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: 12,
  padding: "10px 14px",
  fontSize: 12,
  boxShadow: "0 8px 24px rgba(15, 40, 55, 0.08)",
};

function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="mb-5">
      <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">
        {eyebrow}
      </p>
      <h2 className="text-base font-semibold tracking-tight text-ink">
        {title}
      </h2>
      {description && (
        <p className="mt-1 text-xs leading-5 text-ink-muted">{description}</p>
      )}
    </div>
  );
}

export function ExecutiveDashboard() {
  const [data, setData] = useState<ExecutiveSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError(null);

    api
      .get<ExecutiveSummary>("/api/analytics/executive")
      .then((response) => {
        if (active) {
          setData(response.data);
          setError(null);
        }
      })
      .catch(() => {
        if (active) {
          setError("We couldn't retrieve the executive analytics.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [retryCount]);

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning." : hour < 17 ? "Good afternoon." : "Good evening.";

  if (loading && !data) {
    return (
      <AppLayout title="Executive Overview">
        <div className="space-y-5" aria-label="Loading dashboard">
          <div className="h-48 animate-pulse rounded-2xl bg-surface" />
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="h-32 animate-pulse rounded-2xl border border-border bg-surface"
              />
            ))}
          </div>
          <div className="h-72 animate-pulse rounded-2xl border border-border bg-surface" />
          <p className="text-center text-sm text-ink-muted">
            Loading your clinical overview…
          </p>
        </div>
      </AppLayout>
    );
  }

  if (error && !data) {
    return (
      <AppLayout title="Executive Overview">
        <div className="rounded-2xl border border-border bg-surface p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-2xl text-red-600">
            !
          </div>
          <h2 className="text-lg font-semibold text-ink">
            Dashboard unavailable
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-ink-muted">
            {error} Check that the backend is running and that the analytics
            service is reachable, then try again.
          </p>
          <button
            type="button"
            onClick={() => setRetryCount((count) => count + 1)}
            className="mt-5 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: "var(--color-primary)" }}
          >
            Try again
          </button>
        </div>
      </AppLayout>
    );
  }

  if (!data) {
    return (
      <AppLayout title="Executive Overview">
        <p className="text-sm text-ink-muted">No dashboard data available.</p>
      </AppLayout>
    );
  }

  const trendData = data.admissions_trend.map((item) => ({
    ...item,
    label: formatDay(item.day),
  }));

  const maxDiagnosisCount = Math.max(
    1,
    ...data.top_diagnoses.map((diagnosis) => diagnosis.count),
  );

  const occupancyPercent = data.occupancy_rate * 100;
  const occupancyWarning = data.occupancy_rate > 0.85;

  return (
    <AppLayout title="Executive Overview">
      <div className="space-y-6">
        {/* Welcome panel */}
        <section
          className="relative isolate overflow-hidden rounded-2xl p-6 text-white shadow-sm sm:p-8"
          style={{
            background:
              "linear-gradient(115deg, #102d3a 0%, #164956 58%, #087f8c 100%)",
          }}
        >
          <div
            className="pointer-events-none absolute -right-12 -top-24 h-72 w-72 rounded-full border"
            style={{ borderColor: "rgba(255,255,255,0.12)" }}
          />
          <div
            className="pointer-events-none absolute -right-2 -top-14 h-52 w-52 rounded-full border"
            style={{ borderColor: "rgba(255,255,255,0.10)" }}
          />
          <div
            className="pointer-events-none absolute -bottom-24 right-28 h-48 w-48 rounded-full"
            style={{ background: "rgba(255,255,255,0.04)" }}
          />

          <div className="relative flex flex-col justify-between gap-8 md:flex-row md:items-center">
            <div className="max-w-xl">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-teal-100">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
                Clinical intelligence overview
              </div>
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                {greeting}
              </h2>
              <p className="mt-3 max-w-lg text-sm leading-6 text-white/75">
                Your hospital at a glance. Review patient activity, bed
                occupancy, ward distribution and recorded diagnoses in one
                place.
              </p>
            </div>

            <div className="relative z-10 flex min-w-48 items-center gap-4 self-start rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur-sm md:self-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 text-2xl">
                ✚
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-white/65">
                  Data connection
                </p>
                <p className="mt-1 text-sm font-semibold">Analytics connected</p>
                <p className="mt-1 text-xs text-white/65">
                  Executive summary loaded
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* API refresh warning: keep showing the last successful response */}
        {error && data && (
          <div
            className="flex flex-col gap-3 rounded-xl border p-4 text-sm sm:flex-row sm:items-center sm:justify-between"
            style={{
              borderColor: "rgba(217, 154, 66, 0.35)",
              background: "rgba(217, 154, 66, 0.08)",
              color: "var(--color-ink)",
            }}
          >
            <span>
              Refresh failed. The dashboard is showing the last successfully
              loaded data.
            </span>
            <button
              type="button"
              onClick={() => setRetryCount((count) => count + 1)}
              className="self-start font-semibold underline underline-offset-4 sm:self-auto"
            >
              Retry
            </button>
          </div>
        )}

        {/* KPI cards */}
        <section>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
            <div>
              <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">
                Hospital at a glance
              </p>
              <h2 className="text-base font-semibold text-ink">
                Key performance indicators
              </h2>
            </div>
            <p className="text-xs text-ink-muted">
              Values from the executive analytics API
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Total Patients"
              value={data.total_patients.toLocaleString()}
              sublabel="Patients recorded in the system"
              accent="primary"
              icon="♙"
            />
            <KpiCard
              label="Currently Admitted"
              value={data.currently_admitted.toLocaleString()}
              sublabel={`Total bed capacity: ${data.total_bed_capacity.toLocaleString()}`}
              accent="accent"
              icon="▤"
            />
            <KpiCard
              label="Occupancy Rate"
              value={`${occupancyPercent.toFixed(1)}%`}
              sublabel={
                occupancyWarning
                  ? "High occupancy — review available capacity"
                  : "Based on reported hospital occupancy"
              }
              accent={occupancyWarning ? "danger" : "success"}
              icon="◉"
            />
            <KpiCard
              label="New Patients · 7 Days"
              value={data.new_patients_last_7_days.toLocaleString()}
              sublabel="New patient records over the last 7 days"
              accent="primary"
              icon="↗"
            />
          </div>
        </section>

        {/* Charts */}
        <section>
          <div className="mb-4">
            <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">
              Activity and capacity
            </p>
            <h2 className="text-base font-semibold text-ink">
              Hospital activity
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
            <div className="min-w-0 rounded-2xl border border-border bg-surface p-5 shadow-sm xl:col-span-3">
              <SectionHeading
                eyebrow="Admissions"
                title="Patient admission trend"
                description="Daily admission counts over the available 14-day reporting period."
              />

              {trendData.length === 0 ? (
                <div className="flex h-56 items-center justify-center rounded-xl border border-dashed border-border text-sm text-ink-muted">
                  No admission trend data available.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart
                    data={trendData}
                    margin={{ top: 8, right: 10, left: -12, bottom: 2 }}
                  >
                    <defs>
                      <linearGradient
                        id="admissionsLineGradient"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor="var(--color-primary)"
                          stopOpacity={0.18}
                        />
                        <stop
                          offset="100%"
                          stopColor="var(--color-primary)"
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      vertical={false}
                      strokeDasharray="4 5"
                      stroke="var(--color-border)"
                    />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      stroke="var(--color-ink-muted)"
                      minTickGap={18}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      stroke="var(--color-ink-muted)"
                      allowDecimals={false}
                      width={38}
                    />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      labelStyle={{ color: "var(--color-ink)", fontWeight: 600 }}
                      formatter={(value) => [value, "New patients"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="count"
                      name="New patients"
                      stroke="var(--color-primary)"
                      strokeWidth={3}
                      activeDot={{
                        r: 6,
                        strokeWidth: 3,
                        stroke: "var(--color-surface)",
                      }}
                      dot={{ r: 3, fill: "var(--color-primary)", strokeWidth: 0 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="min-w-0 rounded-2xl border border-border bg-surface p-5 shadow-sm xl:col-span-2">
              <SectionHeading
                eyebrow="Patient distribution"
                title="Ward distribution"
                description="Recorded patient counts by ward."
              />

              {data.ward_distribution.length === 0 ? (
                <div className="flex h-56 items-center justify-center rounded-xl border border-dashed border-border text-sm text-ink-muted">
                  No ward distribution data available.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart
                    data={data.ward_distribution}
                    layout="vertical"
                    margin={{ top: 0, right: 12, left: 2, bottom: 0 }}
                  >
                    <CartesianGrid
                      horizontal={false}
                      strokeDasharray="4 5"
                      stroke="var(--color-border)"
                    />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      stroke="var(--color-ink-muted)"
                      allowDecimals={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="ward"
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      stroke="var(--color-ink-muted)"
                      width={84}
                    />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(value) => [value, "Patients"]}
                    />
                    <Bar
                      dataKey="count"
                      name="Patients"
                      fill="var(--color-primary)"
                      radius={[0, 5, 5, 0]}
                      maxBarSize={22}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </section>

        {/* Diagnoses */}
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-6">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
            <SectionHeading
              eyebrow="Clinical overview"
              title="Top recorded diagnoses"
              description="Most frequently recorded diagnosis descriptions in the available analytics."
            />
            <span className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-ink-muted">
              {data.top_diagnoses.length}{" "}
              {data.top_diagnoses.length === 1 ? "diagnosis" : "diagnoses"}
            </span>
          </div>

          {data.top_diagnoses.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border px-4 py-10 text-center">
              <p className="text-sm font-medium text-ink">
                No diagnoses recorded yet
              </p>
              <p className="mt-1 text-xs text-ink-muted">
                Recorded diagnosis data will appear here when available.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {data.top_diagnoses.map((diagnosis, index) => {
                const barWidth = Math.max(
                  3,
                  (diagnosis.count / maxDiagnosisCount) * 100,
                );

                return (
                  <div
                    key={diagnosis.description}
                    className="grid grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3"
                  >
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-600">
                      {String(index + 1).padStart(2, "0")}
                    </div>

                    <div className="min-w-0">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <p className="truncate text-sm font-medium text-ink">
                          {diagnosis.description}
                        </p>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{
                            width: `${barWidth}%`,
                            background: "var(--color-primary)",
                          }}
                        />
                      </div>
                    </div>

                    <div className="min-w-10 text-right">
                      <p className="tabular-figures text-sm font-semibold text-ink">
                        {diagnosis.count.toLocaleString()}
                      </p>
                      <p className="text-[10px] text-ink-muted">records</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <p className="pb-2 text-center text-[11px] leading-5 text-ink-muted">
          Clinical decision support only. Verify patient information and
          clinical decisions with qualified healthcare professionals.
        </p>
      </div>
    </AppLayout>
  );
}
