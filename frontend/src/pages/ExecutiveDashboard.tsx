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
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ExecutiveDashboard() {
  const [data, setData] = useState<ExecutiveSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ExecutiveSummary>("/api/analytics/executive")
      .then((res) => setData(res.data))
      .catch(() => setError("Could not load analytics. Is the backend running?"));
  }, []);

  if (error) {
    return (
      <AppLayout title="Executive Overview">
        <div className="rounded-xl border border-border bg-surface p-6 text-sm text-danger">
          {error}
        </div>
      </AppLayout>
    );
  }

  if (!data) {
    return (
      <AppLayout title="Executive Overview">
        <div className="text-sm text-ink-muted">Loading dashboard…</div>
      </AppLayout>
    );
  }

  const trendData = data.admissions_trend.map((d) => ({ ...d, label: formatDay(d.day) }));

  return (
    <AppLayout title="Executive Overview">
      {/* KPI row */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label="Total Patients" value={data.total_patients.toLocaleString()} accent="primary" />
        <KpiCard
          label="Currently Admitted"
          value={data.currently_admitted.toLocaleString()}
          sublabel={`of ${data.total_bed_capacity} beds`}
          accent="accent"
        />
        <KpiCard
          label="Occupancy Rate"
          value={`${(data.occupancy_rate * 100).toFixed(1)}%`}
          accent={data.occupancy_rate > 0.85 ? "danger" : "success"}
        />
        <KpiCard
          label="New Patients (7d)"
          value={data.new_patients_last_7_days.toLocaleString()}
          accent="primary"
        />
      </div>

      {/* Charts row */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-surface p-4 shadow-sm lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-ink">Admissions Trend (14 days)</h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="var(--color-ink-muted)" />
              <YAxis tick={{ fontSize: 12 }} stroke="var(--color-ink-muted)" allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  borderRadius: 8,
                  border: "1px solid var(--color-border)",
                  fontSize: 12,
                }}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke="var(--color-primary)"
                strokeWidth={2}
                dot={{ r: 3 }}
                name="New patients"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold text-ink">Ward Distribution</h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.ward_distribution} layout="vertical" margin={{ left: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis type="number" tick={{ fontSize: 12 }} stroke="var(--color-ink-muted)" allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="ward"
                tick={{ fontSize: 12 }}
                stroke="var(--color-ink-muted)"
                width={80}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 8,
                  border: "1px solid var(--color-border)",
                  fontSize: 12,
                }}
              />
              <Bar dataKey="count" fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top diagnoses */}
      <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-ink">Top Diagnoses</h2>
        {data.top_diagnoses.length === 0 ? (
          <p className="text-sm text-ink-muted">No diagnoses recorded yet.</p>
        ) : (
          <ul className="divide-y divide-border">
            {data.top_diagnoses.map((d) => (
              <li key={d.description} className="flex items-center justify-between py-2 text-sm">
                <span className="text-ink">{d.description}</span>
                <span className="tabular-figures font-medium text-ink-muted">{d.count}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppLayout>
  );
}
