import { useEffect, useRef, useState } from "react";
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
          formatter={(v: number) => [`${v?.toFixed(0)} mg/dL`, "Glucose"]}
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
      {factors.length > 0 && (
        <button
          onClick={() => setExpanded((x) => !x)}
          className="mt-2 text-xs text-primary hover:underline"
        >
          {expanded ? "▲ Hide reasons" : "▼ Why this alert?"}
        </button>
      )}
      {expanded && (
        <ul className="mt-2 space-y-1">
          {factors.map((f, i) => (
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

  async function submitDecision(
    idx: number,
    s: InvestigationSuggestion,
    decision: string
  ) {
    await api.post("/api/v1/decisions", {
      patient_id: patientId,
      suggestion_type: s.rule_name,
      rule_id: s.rule_id,
      rule_version: s.rule_version,
      decision,
      reason: reasons[idx] || null,
    });
    onDecision();
  }

  if (suggestions.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        No investigation suggestions available.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-bg text-xs font-medium uppercase tracking-wide text-ink-muted">
            <th className="px-4 py-2">Test / Check</th>
            <th className="px-4 py-2">Status</th>
            <th className="px-4 py-2">Message</th>
            <th className="px-4 py-2">Source</th>
            <th className="px-4 py-2">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {suggestions.map((s, idx) => {
            const ss = STATUS_STYLES[s.status] ?? STATUS_STYLES.OK;
            return (
              <tr key={`${s.rule_id}-${idx}`} className="hover:bg-bg">
                <td className="px-4 py-3">
                  <div className="font-medium text-ink">{s.rule_name}</div>
                  <div className="text-xs text-ink-muted">
                    {s.rule_id} v{s.rule_version}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ss.bg} ${ss.text}`}
                  >
                    {ss.label}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-ink">{s.message}</td>
                <td className="px-4 py-3">
                  {s.source_url ? (
                    <a
                      href={s.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary hover:underline"
                    >
                      {s.source_name.slice(0, 30)}…
                    </a>
                  ) : (
                    <span className="text-xs text-ink-muted">
                      {s.source_name.slice(0, 30)}
                    </span>
                  )}
                  <div className="mt-0.5 text-[10px] italic text-ink-muted">
                    {s.review_status}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <input
                    value={reasons[idx] ?? ""}
                    onChange={(e) =>
                      setReasons((r) => ({ ...r, [idx]: e.target.value }))
                    }
                    placeholder="Reason (optional)"
                    className="mb-1 w-full rounded border border-border bg-bg px-2 py-1 text-xs outline-none focus:border-primary"
                  />
                  <div className="flex gap-1">
                    {["accept", "defer", "override"].map((d) => (
                      <button
                        key={d}
                        onClick={() => submitDecision(idx, s, d)}
                        disabled={pending[idx] === d}
                        className={`rounded px-2 py-0.5 text-xs font-medium capitalize ${
                          d === "accept"
                            ? "bg-success/10 text-success hover:bg-success/20"
                            : d === "defer"
                            ? "bg-accent-soft text-accent hover:bg-accent/20"
                            : "bg-danger-soft text-danger hover:bg-danger/20"
                        }`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
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
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  const pred = twin?.prediction ?? null;
  const investigations = twin?.investigations ?? [];

  return (
    <AppLayout title="GlucoTwin — Diabetes Digital Twin">
      {/* Synthetic data banner */}
      <div className="mb-4 flex items-center gap-2 rounded-lg border border-danger/30 bg-danger-soft px-4 py-2 text-xs font-medium text-danger">
        ⚠ SYNTHETIC DATA — NOT FOR CLINICAL USE. All patients and data are
        entirely synthetic. This prototype does not diagnose, prescribe, or
        order tests. All decisions remain with the clinician.
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
        <div className="mt-8 text-center text-sm text-ink-muted">
          Search for a synthetic T2D patient above to open their digital twin.
        </div>
      )}
    </AppLayout>
  );
}
