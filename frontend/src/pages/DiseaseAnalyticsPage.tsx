import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppLayout } from "../components/AppLayout";
import { api } from "../lib/api";
import type { ExecutiveSummary } from "../lib/types";

function formatNumber(value: number | undefined) {
  return typeof value === "number" ? value.toLocaleString() : "—";
}

function MetricCard({
  label,
  value,
  description,
  icon,
  accent,
}: {
  label: string;
  value: string;
  description: string;
  icon: string;
  accent: string;
}) {
  return (
    <article className="group rounded-2xl border border-[#e3eaf0] bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[#738391]">{label}</p>
          <p className="mt-3 text-3xl font-bold tracking-tight text-[#193342]">
            {value}
          </p>
        </div>
        <div
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl text-xl"
          style={{ color: accent, backgroundColor: `${accent}14` }}
        >
          {icon}
        </div>
      </div>
      <div className="mt-5 border-t border-[#edf1f3] pt-3">
        <p className="text-xs leading-5 text-[#8797a1]">{description}</p>
      </div>
    </article>
  );
}

export function DiseaseAnalyticsPage() {
  const [data, setData] = useState<ExecutiveSummary | null>(null);
  const [error, setError] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadAnalytics = useCallback(async (refresh = false) => {
    if (refresh) setIsRefreshing(true);
    setError(false);

    try {
      const response = await api.get<ExecutiveSummary>(
        "/api/analytics/executive",
      );
      setData(response.data);
    } catch {
      setError(true);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadAnalytics();
  }, [loadAnalytics]);

  const occupancy =
    typeof data?.occupancy_rate === "number"
      ? `${(data.occupancy_rate * 100).toFixed(1)}%`
      : "—";

  return (
    <AppLayout title="Disease Analytics">
      <div className="mb-6 overflow-hidden rounded-2xl bg-[#123c4b] text-white shadow-sm">
        <div className="relative p-6 sm:p-8">
          <div className="pointer-events-none absolute -right-10 -top-20 h-64 w-64 rounded-full border border-white/10" />
          <div className="pointer-events-none absolute -right-2 -top-12 h-48 w-48 rounded-full border border-white/10" />

          <div className="relative flex flex-wrap items-start justify-between gap-5">
            <div className="max-w-2xl">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-[10px] font-bold tracking-[0.16em] text-[#b9e9e4]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#62d4ba]" />
                HOSPITAL INTELLIGENCE
              </div>

              <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
                Disease analytics
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[#d0e1e6]">
                Explore recorded diagnoses, hospital occupancy and ward-level
                patient distribution in one place.
              </p>
            </div>

            <button
              onClick={() => void loadAnalytics(true)}
              disabled={isRefreshing}
              className="relative rounded-xl border border-white/20 bg-white/10 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isRefreshing ? "Refreshing…" : "↻ Refresh data"}
            </button>
          </div>

          <div className="relative mt-7 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/15 pt-4 text-xs text-[#d0e1e6]">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-[#62d4ba]" />
              Connected to hospital analytics API
            </span>
            <span>Descriptive reporting</span>
            <span>Data-backed insights</span>
          </div>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[#f0cdcf] bg-[#fff5f5] p-5"
        >
          <div>
            <p className="font-semibold text-[#b8474c]">
              Analytics could not be loaded
            </p>
            <p className="mt-1 text-sm leading-5 text-[#926b6d]">
              Check that the backend is running, then try again.
            </p>
          </div>
          <button
            onClick={() => void loadAnalytics(true)}
            disabled={isRefreshing}
            className="rounded-xl border border-[#e7babc] bg-white px-4 py-2.5 text-sm font-semibold text-[#a83e44] disabled:opacity-60"
          >
            Try again
          </button>
        </div>
      )}

      {!data && !error && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[1, 2, 3].map((item) => (
            <div
              key={item}
              className="animate-pulse rounded-2xl border border-[#e3eaf0] bg-white p-6"
            >
              <div className="h-4 w-28 rounded bg-[#edf2f4]" />
              <div className="mt-5 h-9 w-24 rounded bg-[#edf2f4]" />
              <div className="mt-5 h-3 w-40 rounded bg-[#f1f4f6]" />
            </div>
          ))}
          <div className="rounded-2xl border border-[#e3eaf0] bg-white p-6 text-sm text-[#738391] sm:col-span-3">
            Loading hospital analytics…
          </div>
        </div>
      )}

      {data && (
        <>
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-lg font-bold text-[#193342]">
                Hospital at a glance
              </h3>
              <p className="mt-1 text-sm text-[#8797a1]">
                Summary based on the data returned by your backend.
              </p>
            </div>
            <span className="rounded-full border border-[#dce9e9] bg-[#f0f8f7] px-3 py-1.5 text-xs font-semibold text-[#087f8c]">
              Live API summary
            </span>
          </div>

          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <MetricCard
              label="Diagnoses tracked"
              value={formatNumber(data.top_diagnoses?.length)}
              description="Diagnosis labels represented in the current summary"
              icon="⌕"
              accent="#087f8c"
            />
            <MetricCard
              label="Currently admitted"
              value={formatNumber(data.currently_admitted)}
              description="Patients currently recorded as admitted"
              icon="＋"
              accent="#397bb5"
            />
            <MetricCard
              label="Bed occupancy"
              value={occupancy}
              description={`${formatNumber(data.total_bed_capacity)} total bed capacity`}
              icon="▦"
              accent="#bd8840"
            />
          </div>

          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#e3f5f5] text-lg text-[#087f8c]">
              ◫
            </div>
            <div>
              <h3 className="font-bold text-[#193342]">
                Patterns and distribution
              </h3>
              <p className="mt-1 text-xs text-[#8797a1]">
                Explore the diagnosis and ward data returned by the API.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.35fr_1fr]">
            <section className="min-w-0 rounded-2xl border border-[#e3eaf0] bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-bold text-[#193342]">
                    Most recorded diagnoses
                  </h3>
                  <span className="rounded-lg bg-[#edf7f7] px-2.5 py-1 text-xs font-semibold text-[#087f8c]">
                    {data.top_diagnoses.length} labels
                  </span>
                </div>
                <p className="mt-2 text-xs leading-5 text-[#8797a1]">
                  Recorded case counts for diagnoses represented in the
                  current dataset.
                </p>
              </div>

              {data.top_diagnoses.length > 0 ? (
                <ResponsiveContainer width="100%" height={330}>
                  <BarChart
                    data={data.top_diagnoses}
                    layout="vertical"
                    margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="#e8eef1"
                      horizontal={false}
                    />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 11, fill: "#8797a1" }}
                      axisLine={false}
                      tickLine={false}
                      allowDecimals={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="description"
                      width={130}
                      tick={{ fontSize: 10, fill: "#657984" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "#f2f8f8" }}
                      contentStyle={{
                        border: "1px solid #e3eaf0",
                        borderRadius: 12,
                        fontSize: 12,
                        boxShadow: "0 8px 24px rgba(25,51,66,0.08)",
                      }}
                    />
                    <Bar
                      dataKey="count"
                      name="Recorded cases"
                      fill="#087f8c"
                      radius={[0, 6, 6, 0]}
                      maxBarSize={25}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex min-h-64 items-center justify-center rounded-xl bg-[#f8fafb] px-5 text-center text-sm text-[#8797a1]">
                  No diagnosis data available yet.
                </div>
              )}

              <div className="mt-3 flex items-center gap-2 border-t border-[#edf1f3] pt-4 text-xs text-[#8797a1]">
                <span className="h-2 w-2 rounded-sm bg-[#087f8c]" />
                Recorded cases in the current summary
              </div>
            </section>

            <section className="min-w-0 rounded-2xl border border-[#e3eaf0] bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5">
                <h3 className="font-bold text-[#193342]">Ward overview</h3>
                <p className="mt-2 text-xs leading-5 text-[#8797a1]">
                  Patient counts by ward, as reported by the backend.
                </p>
              </div>

              {data.ward_distribution.length > 0 ? (
                <div className="space-y-4">
                  {data.ward_distribution.map((ward) => {
                    const maxCount = Math.max(
                      1,
                      ...data.ward_distribution.map((item) => item.count),
                    );
                    const width = Math.max(
                      0,
                      Math.min(100, (ward.count / maxCount) * 100),
                    );

                    return (
                      <div key={ward.ward}>
                        <div className="mb-2 flex items-center justify-between gap-3">
                          <span className="min-w-0 truncate text-sm font-medium text-[#526b78]">
                            {ward.ward}
                          </span>
                          <span className="shrink-0 text-sm font-bold tabular-nums text-[#193342]">
                            {ward.count.toLocaleString()}
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-[#edf2f4]">
                          <div
                            className="h-full rounded-full bg-[#3a9da0] transition-all"
                            style={{ width: `${width}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-xl bg-[#f8fafb] p-5 text-sm text-[#8797a1]">
                  No ward distribution available.
                </div>
              )}

              <div className="mt-6 space-y-0 border-t border-[#edf1f3] pt-2">
                <div className="flex items-center justify-between gap-3 border-b border-[#edf1f3] py-4">
                  <span className="text-sm text-[#738391]">
                    Total patients in system
                  </span>
                  <strong className="text-sm text-[#193342]">
                    {formatNumber(data.total_patients)}
                  </strong>
                </div>
                <div className="flex items-center justify-between gap-3 py-4">
                  <span className="text-sm text-[#738391]">
                    New patients · last 7 days
                  </span>
                  <strong className="text-sm text-[#193342]">
                    {formatNumber(data.new_patients_last_7_days)}
                  </strong>
                </div>
              </div>
            </section>
          </div>

          <div className="mt-5 rounded-xl border border-[#e3eaf0] bg-[#f8fafb] p-4">
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-[#738391]">
                i
              </span>
              <div>
                <p className="text-xs font-semibold text-[#526b78]">
                  How to interpret these insights
                </p>
                <p className="mt-1 text-xs leading-5 text-[#8797a1]">
                  These summaries describe recorded hospital data only. They
                  do not establish a diagnosis, explain causation, or predict
                  an individual patient's disease risk. Occupancy and counts
                  reflect the values returned by the backend.
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </AppLayout>
  );
}
