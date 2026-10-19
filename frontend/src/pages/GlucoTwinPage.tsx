import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppLayout } from "../components/AppLayout";
import { api } from "../lib/api";
import type {
  CgmReading,
  GlucoPatient,
  InvestigationSuggestion,
  TwinState,
} from "../lib/types";

// ── Constants ─────────────────────────────────────────────────────────────────
const HYPER = 180;
const HYPO = 70;

const RISK_STYLES: Record<
  string,
  { bg: string; text: string; border: string; label: string }
> = {
  high: {
    bg: "bg-danger-soft",
    text: "text-danger",
    border: "border-l-danger",
    label: "High risk",
  },
  medium: {
    bg: "bg-accent-soft",
    text: "text-accent",
    border: "border-l-accent",
    label: "Medium risk",
  },
  low: {
    bg: "bg-primary-soft",
    text: "text-primary-dark",
    border: "border-l-primary",
    label: "Low risk",
  },
  unknown: {
    bg: "bg-bg",
    text: "text-ink-muted",
    border: "border-l-border",
    label: "Unknown",
  },
};

const STATUS_STYLES: Record<
  string,
  { bg: string; text: string; label: string }
> = {
  DUE: { bg: "bg-danger-soft", text: "text-danger", label: "DUE" },
  REFER: { bg: "bg-accent-soft", text: "text-accent", label: "REFER" },
  OVERRIDE: { bg: "bg-danger-soft", text: "text-danger", label: "REVIEW" },
  RECENT: { bg: "bg-primary-soft", text: "text-primary-dark", label: "RECENT" },
  MISSING_DATA: {
    bg: "bg-bg",
    text: "text-ink-muted",
    label: "MISSING DATA",
  },
  OK: { bg: "bg-bg", text: "text-ink-muted", label: "OK" },
};

// ── Patient selector ─────────────────────────────────────────────────────────

function PatientSelector({
  selected,
  onSelect,
}: {
  selected: GlucoPatient | null;
  onSelect: (p: GlucoPatient) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GlucoPatient[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (query.length < 3) {
      setResults([]);
      return;
    }
    const h = setTimeout(() => {
      setLoading(true);
      api
        .get<{ items: GlucoPatient[] }>("/api/v1/patients", {
          params: { search: query, page: 1, page_size: 10 },
        })
        .then((r) => setResults(r.data.items))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(h);
  }, [query]);

  function choose(p: GlucoPatient) {
    onSelect(p);
    setQuery("");
    setResults([]);
  }

  return (
    <div className="relative">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search patient ID (e.g. SYN-0001)…"
        className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
      />
      {loading && (
        <p className="mt-1 text-xs text-ink-muted">Searching…</p>
      )}
      {results.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-border bg-surface shadow-lg">
          {results.map((p) => (
            <li key={p.patient_id}>
              <button
                onClick={() => choose(p)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-bg"
              >
                <span className="font-medium text-ink">{p.patient_id}</span>
                <span className="text-xs text-ink-muted">
                  {p.sex} · Age {Math.round(p.age)} · HbA1c{" "}
                  {p.hba1c_latest?.toFixed(1) ?? "N/A"}%
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected && (
        <div className="mt-2 text-xs text-ink-muted">
          Selected:{" "}
          <span className="font-semibold text-ink">{selected.patient_id}</span>{" "}
          — Age {Math.round(selected.age)}, BMI {selected.bmi.toFixed(1)},
          HbA1c {selected.hba1c_latest?.toFixed(1) ?? "N/A"}%
          {selected.insulin_flag && (
            <span className="ml-1 rounded-full bg-danger-soft px-1.5 py-0.5 text-danger">
              Insulin
            </span>
          )}
          {selected.sulfonylurea_flag && (
            <span className="ml-1 rounded-full bg-accent-soft px-1.5 py-0.5 text-accent">
              SU
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ── CGM chart ─────────────────────────────────────────────────────────────────

function CgmChart({
  readings,
  windowHours,
}: {
  readings: CgmReading[];
  windowHours: number;
}) {
  const cutoff = Date.now() - windowHours * 3600 * 1000;
  const data = readings
    .filter((r) => new Date(r.timestamp).getTime() >= cutoff)
    .map((r) => ({
      t: new Date(r.timestamp).getTime(),
      label: new Date(r.timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      glucose: r.glucose_mg_dl,
    }));

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-ink-muted">
        No CGM data in selected window
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ left: 0, right: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10 }}
          stroke="var(--color-ink-muted)"
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[40, 320]}
          tick={{ fontSize: 10 }}
          stroke="var(--color-ink-muted)"
          label={{
            value: "mg/dL",
            angle: -90,
            position: "insideLeft",
            style: { fontSize: 10 },
          }}
        />
        <Tooltip
          formatter={(v) => [`${Number(v ?? 0).toFixed(0)} mg/dL`, "Glucose"]}
          contentStyle={{
            borderRadius: 8,
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        />
        <ReferenceLine
          y={HYPER}
          stroke="var(--color-danger)"
          strokeDasharray="4 3"
          label={{ value: "180", position: "right", fontSize: 10 }}
        />
        <ReferenceLine
          y={HYPO}
          stroke="var(--color-accent)"
          strokeDasharray="4 3"
          label={{ value: "70", position: "right", fontSize: 10 }}
        />
        <Line
          type="monotone"
          dataKey="glucose"
          stroke="var(--color-primary)"
          strokeWidth={2}
          dot={false}
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Risk card ─────────────────────────────────────────────────────────────────

function RiskCard({
  label,
  prob,
  band,
  factors,
}: {
  label: string;
  prob: number | null;
  band: string;
  factors: string[];
}) {
  const [expanded, setExpanded] = useState(false);
  const safeFactors = Array.isArray(factors) ? factors : [];
  const style = RISK_STYLES[band] ?? RISK_STYLES.unknown;

  return (
    <div
      className={`rounded-xl border border-border border-l-4 ${style.border} p-4 shadow-sm`}
    >
      <div className="flex items-baseline justify-between">
        <div>
          <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            {label}
          </span>
          <span
            className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${style.bg} ${style.text}`}
          >
            {style.label}
          </span>
        </div>
        <span className="tabular-figures text-2xl font-semibold text-ink">
          {prob !== null ? `${(prob * 100).toFixed(0)}%` : "—"}
        </span>
      </div>
      {safeFactors.length > 0 && (
        <button
          onClick={() => setExpanded((x) => !x)}
          className="mt-2 text-xs text-primary hover:underline"
        >
          {expanded ? "▲ Hide reasons" : "▼ Why this alert?"}
        </button>
      )}
      {expanded && (
        <ul className="mt-2 space-y-1">
          {safeFactors.map((f, i) => (
            <li key={i} className="text-xs text-ink">
              • {f}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Twin state panel ──────────────────────────────────────────────────────────

function TwinStatePanel({ state }: { state: TwinState }) {
  const tir = state.time_in_range_7d;
  const tirColor =
    tir === null
      ? "text-ink-muted"
      : tir >= 0.7
      ? "text-success"
      : "text-danger";

  return (
    <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
      <div className="rounded-lg border border-border bg-bg p-3">
        <div className="text-xs text-ink-muted">Time in Range (7d)</div>
        <div className={`mt-0.5 text-xl font-semibold ${tirColor}`}>
          {tir !== null ? `${(tir * 100).toFixed(0)}%` : "—"}
        </div>
        <div className="text-xs text-ink-muted">Target ≥ 70%</div>
      </div>
      <div className="rounded-lg border border-border bg-bg p-3">
        <div className="text-xs text-ink-muted">Hypo Events (14d)</div>
        <div
          className={`mt-0.5 text-xl font-semibold ${
            (state.hypo_events_14d ?? 0) >= 2 ? "text-danger" : "text-ink"
          }`}
        >
          {state.hypo_events_14d ?? 0}
        </div>
      </div>
      <div className="rounded-lg border border-border bg-bg p-3">
        <div className="text-xs text-ink-muted">Avg Sleep (7d)</div>
        <div className="mt-0.5 text-xl font-semibold text-ink">
          {state.avg_sleep_h !== null
            ? `${state.avg_sleep_h.toFixed(1)} h`
            : "—"}
        </div>
      </div>
      <div className="rounded-lg border border-border bg-bg p-3">
        <div className="text-xs text-ink-muted">Steps Today</div>
        <div className="mt-0.5 text-xl font-semibold text-ink">
          {state.steps_today !== null
            ? Math.round(state.steps_today).toLocaleString()
            : "—"}
        </div>
      </div>
      <div className="rounded-lg border border-border bg-bg p-3">
        <div className="text-xs text-ink-muted">HRV Trend</div>
        <div className="mt-0.5 text-xl font-semibold text-ink">
          {state.hrv_trend === 1
            ? "↑ Improving"
            : state.hrv_trend === -1
            ? "↓ Declining"
            : "→ Stable"}
        </div>
      </div>
      <div className="rounded-lg border border-border bg-bg p-3">
        <div className="text-xs text-ink-muted">Confidence</div>
        <div
          className={`mt-0.5 text-sm font-semibold ${
            state.confidence_flag === "ok" ? "text-success" : "text-accent"
          }`}
        >
          {state.confidence_flag === "ok"
            ? "Good"
            : state.confidence_flag === "low_confidence"
            ? "Low"
            : "Data gap"}
          {state.data_gap_flag && (
            <span className="ml-1 text-xs text-danger">⚠ Gap</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Investigation suggestions table ──────────────────────────────────────────

function InvestigationsTable({
  suggestions,
  patientId,
  onDecision,
}: {
  suggestions: InvestigationSuggestion[];
  patientId: string;
  onDecision: () => void;
}) {
  const [pending, setPending] = useState<Record<number, string>>({});
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});
  const [success, setSuccess] = useState<Record<number, string>>({});

  async function submitDecision(
    idx: number,
    s: InvestigationSuggestion,
    decision: string
  ) {
    setPending((p) => ({ ...p, [idx]: decision }));
    setErrors((e) => ({ ...e, [idx]: "" }));
    setSuccess((v) => ({ ...v, [idx]: "" }));

    try {
      await api.post("/api/v1/decisions", {
        patient_id: patientId,
        suggestion_type: s.rule_name,
        rule_id: s.rule_id,
        rule_version: s.rule_version,
        decision,
        reason: reasons[idx]?.trim() || null,
      });

      setSuccess((v) => ({
        ...v,
        [idx]: `Decision recorded: ${decision}.`,
      }));
      onDecision();
    } catch {
      setErrors((e) => ({
        ...e,
        [idx]: "Could not save this decision. Please try again.",
      }));
    } finally {
      setPending((p) => {
        const next = { ...p };
        delete next[idx];
        return next;
      });
    }
  }

  if (suggestions.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-bg px-5 py-8 text-center">
        <p className="text-sm font-medium text-ink">
          No review suggestions available
        </p>
        <p className="mt-1 text-xs text-ink-muted">
          Suggestions will appear here when supported by the available patient data.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-ink-muted">
          {suggestions.length} review {suggestions.length === 1 ? "item" : "items"}
        </p>
        <p className="text-xs text-ink-muted">
          Decisions are recorded in the audit log.
        </p>
      </div>

      {suggestions.map((s, idx) => {
        const ss = STATUS_STYLES[s.status] ?? STATUS_STYLES.OK;
        const busy = Boolean(pending[idx]);

        return (
          <article
            key={`${s.rule_id}-${idx}`}
            className="overflow-hidden rounded-xl border border-border bg-surface transition-shadow hover:shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold leading-5 text-ink">
                  {s.rule_name}
                </h3>
                <p className="mt-1 text-xs text-ink-muted">
                  Rule {s.rule_id} · Version {s.rule_version}
                </p>
              </div>
              <span
                className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${ss.bg} ${ss.text}`}
              >
                {ss.label}
              </span>
            </div>

            <div className="grid gap-4 px-4 py-4 sm:px-5 lg:grid-cols-[minmax(0,1fr)_minmax(220px,0.7fr)]">
              <div className="min-w-0">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
                  Clinical context
                </p>
                <p className="text-sm leading-6 text-ink">{s.message}</p>

                <div className="mt-3">
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
                    Evidence source
                  </p>
                  {s.source_url ? (
                    <a
                      href={s.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex max-w-full items-center gap-1 break-words text-xs font-medium text-primary hover:underline"
                    >
                      <span>{s.source_name || "View clinical reference"}</span>
                      <span aria-hidden="true">↗</span>
                    </a>
                  ) : (
                    <span className="text-xs text-ink-muted">
                      {s.source_name || "No source provided"}
                    </span>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-border bg-bg/60 p-3">
                <label
                  htmlFor={`review-reason-${idx}`}
                  className="mb-1.5 block text-xs font-medium text-ink"
                >
                  Clinician note <span className="font-normal text-ink-muted">(optional)</span>
                </label>
                <textarea
                  id={`review-reason-${idx}`}
                  value={reasons[idx] ?? ""}
                  onChange={(e) =>
                    setReasons((r) => ({ ...r, [idx]: e.target.value }))
                  }
                  placeholder="Add a reason or review note…"
                  rows={2}
                  disabled={busy}
                  className="w-full resize-y rounded-lg border border-border bg-surface px-3 py-2 text-xs text-ink outline-none placeholder:text-ink-muted focus:border-primary"
                />

                <p className="mb-2 mt-3 text-[11px] font-medium text-ink-muted">
                  Record your decision
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {(["accept", "defer", "override"] as const).map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => void submitDecision(idx, s, d)}
                      disabled={busy}
                      className={`min-h-9 rounded-lg border px-2 py-2 text-xs font-semibold capitalize transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                        d === "accept"
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          : d === "defer"
                          ? "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100"
                          : "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                      }`}
                    >
                      {busy && pending[idx] === d
                        ? "Saving…"
                        : d === "override"
                        ? "Override"
                        : d === "accept"
                        ? "Accept"
                        : "Defer"}
                    </button>
                  ))}
                </div>

                {errors[idx] && (
                  <p role="alert" className="mt-2 text-xs text-danger">
                    {errors[idx]}
                  </p>
                )}
                {success[idx] && (
                  <p role="status" className="mt-2 text-xs text-success">
                    {success[idx]}
                  </p>
                )}
              </div>
            </div>

            <div className="border-t border-border bg-bg/50 px-4 py-2 sm:px-5">
              <p className="text-[11px] text-ink-muted">
                Review status: {s.review_status || "Pending clinician review"}
              </p>
            </div>
          </article>
        );
      })}
    </div>
  );
}

// ── Audit log panel ───────────────────────────────────────────────────────────

function AuditLog({ patientId }: { patientId: string }) {
  const [entries, setEntries] = useState<
    { id: number; decision: string; suggestion_type: string; reason: string; created_at: string }[]
  >([]);

  useEffect(() => {
    api
      .get<{ entries: typeof entries }>("/api/v1/audit", {
        params: { patient_id: patientId },
      })
      .then((r) => setEntries(r.data.entries))
      .catch(() => {});
  }, [patientId]);

  if (entries.length === 0)
    return (
      <p className="text-sm text-ink-muted">No decisions recorded yet.</p>
    );

  return (
    <ul className="divide-y divide-border text-sm">
      {entries.slice(0, 20).map((e) => (
        <li key={e.id} className="flex items-start justify-between py-2">
          <div>
            <span
              className={`mr-2 rounded px-1.5 py-0.5 text-xs font-semibold capitalize ${
                e.decision === "accept"
                  ? "bg-success/10 text-success"
                  : e.decision === "defer"
                  ? "bg-accent-soft text-accent"
                  : "bg-danger-soft text-danger"
              }`}
            >
              {e.decision}
            </span>
            <span className="text-ink">{e.suggestion_type}</span>
            {e.reason && (
              <span className="ml-1 text-xs text-ink-muted">— {e.reason}</span>
            )}
          </div>
          <span className="ml-4 shrink-0 text-xs text-ink-muted">
            {new Date(e.created_at).toLocaleString()}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function GlucoTwinPage() {
  const [patient, setPatient] = useState<GlucoPatient | null>(null);
  const [twin, setTwin] = useState<TwinState | null>(null);
  const [readings, setReadings] = useState<CgmReading[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [windowHours, setWindowHours] = useState(6);
  const [advancing, setAdvancing] = useState(false);
  const [auditKey, setAuditKey] = useState(0);

  function loadPatientData(p: GlucoPatient) {
    setLoading(true);
    setError(null);
    const pid = p.patient_id;
    Promise.all([
      api.get<TwinState>(`/api/v1/twin/${pid}`),
      api.get<{ readings: CgmReading[] }>(`/api/v1/patients/${pid}/cgm`),
    ])
      .then(([twinRes, cgmRes]) => {
        setTwin(twinRes.data);
        setReadings(cgmRes.data.readings);
      })
      .catch((e) => {
        if (e?.response?.status === 503) {
          setError("GlucoTwin models not trained yet. Run: python twin/model_train.py");
        } else {
          setError("Could not load patient data. Is the backend running?");
        }
      })
      .finally(() => setLoading(false));
  }

  function handleSelect(p: GlucoPatient) {
    setPatient(p);
    loadPatientData(p);
  }

  async function handleAdvance() {
    if (!patient) return;
    setAdvancing(true);
    try {
      await api.post(`/api/v1/demo/advance/${patient.patient_id}`, null, {
        params: { n_minutes: 30 },
      });
      loadPatientData(patient);
    } finally {
      setAdvancing(false);
    }
  }

  function handleDecision() {
    setAuditKey((k) => k + 1);
    if (patient) loadPatientData(patient);
  }


  // Read-only Nightscout sync + automatic twin refresh every 30 seconds.
  useEffect(() => {
    if (!patient) return;
    let active = true;
    const refreshLive = async () => {
      try {
        if (import.meta.env.VITE_NIGHTSCOUT_ENABLED === "true") { await api.post("/api/v1/integrations/nightscout/sync", { patient_id: patient.patient_id }); }
      } catch {
        // Expected until the live connector is configured; keep last known data.
      }
      if (!active) return;
      try {
        const [twinRes, cgmRes] = await Promise.all([
          api.get<TwinState>(`/api/v1/twin/${patient.patient_id}`),
          api.get<{ readings: CgmReading[] }>(`/api/v1/patients/${patient.patient_id}/cgm`),
        ]);
        if (active) { setTwin(twinRes.data); setReadings(cgmRes.data.readings); }
      } catch {
        // Preserve last successful UI state during a temporary network issue.
      }
    };
    void refreshLive();
    const timer = window.setInterval(() => void refreshLive(), 30_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [patient?.patient_id]);

  const pred = twin?.prediction ?? null;
  const investigations = twin?.investigations ?? [];

  return (
    <AppLayout title="GlucoTwin — Diabetes Digital Twin">
      {/* Prototype safety banner */}
      <div className="mb-4 flex items-center gap-2 rounded-lg border border-danger/30 bg-danger-soft px-4 py-2 text-xs font-medium text-danger">
        Prototype insights · Not for clinical decision-making. Predictions are experimental and
        must not be used to diagnose or guide treatment. Verify the data source
        and readings. All decisions remain with the clinician.
      </div>

      {/* Patient selector */}
      <div className="mb-5 rounded-xl border border-border bg-surface p-4 shadow-sm">
        <h2 className="mb-2 text-sm font-semibold text-ink">Select Patient</h2>
        <PatientSelector selected={patient} onSelect={handleSelect} />
      </div>

      {loading && (
        <div className="text-sm text-ink-muted">Loading patient twin…</div>
      )}
      {error && (
        <div className="rounded-xl border border-border bg-danger-soft p-4 text-sm text-danger">
          {error}
        </div>
      )}

      {!loading && !error && patient && twin && (
        <div className="space-y-5">
          {/* Patient card */}
          <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-ink">
                  {patient.patient_id}
                </h2>
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-ink-muted">
                  <span>Age {Math.round(patient.age)}</span>
                  <span>{patient.sex === "M" ? "Male" : "Female"}</span>
                  <span>BMI {patient.bmi.toFixed(1)}</span>
                  <span>T2D {patient.diabetes_duration_years.toFixed(1)} yrs</span>
                  <span>HbA1c {patient.hba1c_latest?.toFixed(1) ?? "N/A"}%</span>
                  {patient.hypertension && (
                    <span className="rounded-full bg-accent-soft px-1.5 py-0.5 text-accent">
                      HTN
                    </span>
                  )}
                  {patient.ckd_stage > 0 && (
                    <span className="rounded-full bg-accent-soft px-1.5 py-0.5 text-accent">
                      CKD {patient.ckd_stage}
                    </span>
                  )}
                  {patient.insulin_flag && (
                    <span className="rounded-full bg-danger-soft px-1.5 py-0.5 text-danger">
                      Insulin
                    </span>
                  )}
                  {patient.sulfonylurea_flag && (
                    <span className="rounded-full bg-danger-soft px-1.5 py-0.5 text-danger">
                      Sulfonylurea
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-ink-muted">
                  Genetic risk:{" "}
                  <strong>{(patient.genetic_risk_score * 100).toFixed(0)}%</strong>
                </span>
                <button
                  onClick={handleAdvance}
                  disabled={advancing}
                  className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-dark disabled:opacity-50"
                >
                  {advancing ? "Advancing…" : "▶ Play 30 min"}
                </button>
              </div>
            </div>
          </div>

          {/* CGM chart + window selector */}
          <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">
                Live CGM + Forecast
              </h2>
              <div className="flex gap-1">
                {[6, 12, 24].map((h) => (
                  <button
                    key={h}
                    onClick={() => setWindowHours(h)}
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      windowHours === h
                        ? "bg-primary text-white"
                        : "border border-border text-ink-muted"
                    }`}
                  >
                    {h}h
                  </button>
                ))}
              </div>
            </div>
            {readings.length > 0 ? (
              <CgmChart readings={readings} windowHours={windowHours} />
            ) : (
              <div className="flex h-48 items-center justify-center text-sm text-ink-muted">
                No CGM readings loaded. Press ▶ Play to load data.
              </div>
            )}
            <p className="mt-2 text-[10px] text-ink-muted">
              Red dashed = 180 mg/dL (hyperglycaemia threshold) ·
              Orange dashed = 70 mg/dL (hypoglycaemia threshold)
            </p>
          </div>

          {/* Risk alerts */}
          {pred ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <RiskCard
                label="Hyperglycaemia risk (2 h)"
                prob={pred.p_hyper_120}
                band={pred.risk_band_hyper}
                factors={pred.top_factors_hyper}
              />
              <RiskCard
                label="Hypoglycaemia risk (2 h)"
                prob={pred.p_hypo_120}
                band={pred.risk_band_hypo}
                factors={pred.top_factors_hypo}
              />
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-surface p-4 text-sm text-ink-muted">
              Predictions not yet available. Train the model first:{" "}
              <code>python twin/model_train.py</code>
            </div>
          )}

          {/* Twin state summary */}
          <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-ink">
              Twin State Summary
            </h2>
            <TwinStatePanel state={twin} />
          </div>

          {/* Investigation suggestions */}
          <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-ink">
              Investigation Suggestions
            </h2>
            <p className="mb-3 text-xs italic text-ink-muted">
              These are candidate review prompts only. All suggestions are
              pending clinician review and carry rule IDs and evidence sources.
              No investigation is ordered automatically. The clinician decides.
            </p>
            <InvestigationsTable
              suggestions={investigations}
              patientId={patient.patient_id}
              onDecision={handleDecision}
            />
          </div>

          {/* Audit log */}
          <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-ink">
              Clinician Decision Log
            </h2>
            <AuditLog key={auditKey} patientId={patient.patient_id} />
          </div>
        </div>
      )}

      {!patient && !loading && (
        <div className="mt-8 rounded-xl border border-border bg-surface p-6 text-center text-sm text-ink-muted">
          <p className="mb-2 font-semibold text-ink">Open your GlucoTwin</p>
          <p>Select a patient above to view their digital twin.</p>
          <p className="mt-2">
            Live glucose readings require a configured Nightscout connection
            and a matching patient profile. If the connection is unavailable,
            live readings may not appear.
          </p>
        </div>
      )}
    </AppLayout>
  );
}
