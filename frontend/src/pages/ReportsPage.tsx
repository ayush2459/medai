import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AppLayout } from "../components/AppLayout";
import { api } from "../lib/api";
import type { ExecutiveSummary, PaginatedPatients, GlucoPatient, TwinState, IcuRiskResponse } from "../lib/types";

type ReportData = {
  executive: ExecutiveSummary | null;
  patients: PaginatedPatients | null;
  gluco: { total: number; items: GlucoPatient[] } | null;
  twins: Array<{ patientId: string; state: TwinState | null }>;
  icu: Array<{ patientId: string; result: IcuRiskResponse | null }>;
  updatedAt: Date | null;
  errors: string[];
};

const emptyData: ReportData = { executive: null, patients: null, gluco: null, twins: [], icu: [], updatedAt: null, errors: [] };
const n = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : null;
const fmt = (value: unknown) => n(value)?.toLocaleString() ?? "—";
const pct = (value: unknown) => n(value) === null ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
const dateTime = (date: Date | null) => date ? date.toLocaleString([], { dateStyle: "medium", timeStyle: "medium" }) : "Waiting for first refresh";

function Metric({ label, value, note, tone = "teal" }: { label: string; value: string; note: string; tone?: "teal" | "blue" | "amber" | "violet" }) {
  const tones = { teal: "border-teal-200 bg-teal-50 text-teal-700", blue: "border-sky-200 bg-sky-50 text-sky-700", amber: "border-amber-200 bg-amber-50 text-amber-700", violet: "border-violet-200 bg-violet-50 text-violet-700" };
  return <div className={`rounded-2xl border p-5 ${tones[tone]}`}><p className="text-[10px] font-bold uppercase tracking-[.19em] opacity-75">{label}</p><p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 tabular-nums">{value}</p><p className="mt-2 text-xs leading-5 text-slate-500">{note}</p></div>;
}

function Section({ eyebrow, title, note, children }: { eyebrow: string; title: string; note?: string; children: ReactNode }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_18px_55px_rgba(0,0,0,.18)] sm:p-6"><div className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-teal-700">{eyebrow}</p><h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-800">{title}</h2>{note && <p className="mt-1 text-xs leading-5 text-slate-500">{note}</p>}</div></div>{children}</section>;
}

export function ReportsPage() {
  const [data, setData] = useState<ReportData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  const refresh = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true); else setLoading(true);
    setLastError(null);

    try {
      const errors: string[] = [];
      // Bound each request so a slow/unreachable endpoint cannot leave the page
      // permanently stuck in CONNECTING.
      const [executiveRes, patientsRes, glucoRes] = await Promise.allSettled([
        api.get<ExecutiveSummary>("/api/analytics/executive", { timeout: 15000 }),
        api.get<PaginatedPatients>("/api/patients", { params: { page: 1, page_size: 100 }, timeout: 15000 }),
        api.get<{ total: number; items: GlucoPatient[] }>("/api/v1/patients", { params: { page: 1, page_size: 50 }, timeout: 15000 }),
      ]);
      const executive = executiveRes.status === "fulfilled" ? executiveRes.value.data : null;
      const patients = patientsRes.status === "fulfilled" ? patientsRes.value.data : null;
      const gluco = glucoRes.status === "fulfilled" ? glucoRes.value.data : null;
      if (!executive) errors.push("Overview / disease analytics could not be loaded.");
      if (!patients) errors.push("Patient directory could not be loaded.");
      if (!gluco) errors.push("GlucoTwin cohort could not be loaded.");

      const glucoItems = gluco?.items ?? [];
      const twinTargets = glucoItems.slice(0, 8);
      const patientTargets = (patients?.items ?? []).slice(0, 10);
      const [twinResults, icuResults] = await Promise.all([
        Promise.allSettled(twinTargets.map((p) => api.get<TwinState>(`/api/v1/twin/${encodeURIComponent(p.patient_id)}`, { timeout: 10000 }))),
        Promise.allSettled(patientTargets.map((p) => api.get<IcuRiskResponse>(`/api/ml/icu-risk/${encodeURIComponent(p.id)}`, { timeout: 10000 }))),
      ]);
      const twins = twinResults.map((result, i) => ({ patientId: twinTargets[i].patient_id, state: result.status === "fulfilled" ? result.value.data : null }));
      const icu = icuResults.map((result, i) => ({ patientId: patientTargets[i].id, result: result.status === "fulfilled" ? result.value.data : null }));
      const next: ReportData = { executive, patients, gluco, twins, icu, updatedAt: new Date(), errors };
      setData(next);
      setLastError(errors.length === 3
        ? "The report could not reach its data sources. Check your session and backend."
        : errors.length
          ? "Some sections are unavailable; the report is showing the data sources that responded."
          : null);
    } catch (error) {
      console.error("MedIntel report refresh failed:", error);
      setLastError("Report refresh encountered an unexpected error. Check the browser console and backend.");
      // Mark the attempt complete so the UI does not remain stuck forever.
      setData((current) => current.updatedAt ? current : { ...emptyData, updatedAt: new Date(), errors: ["Unexpected refresh error; values are unavailable."] });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(true), 30_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const exec = data.executive;
  const patients = data.patients;
  const gluco = data.gluco;
  const admittedPercent = exec && exec.total_patients > 0 ? (exec.currently_admitted / exec.total_patients) * 100 : null;
  const riskSummary = useMemo(() => {
    const available = data.icu.map((x) => x.result).filter((x): x is IcuRiskResponse => !!x);
    return { available: available.length, high: available.filter((x) => x.risk_level === "high").length, medium: available.filter((x) => x.risk_level === "medium").length, low: available.filter((x) => x.risk_level === "low").length };
  }, [data.icu]);
  const twinSummary = useMemo(() => {
    const available = data.twins.map((x) => x.state).filter((x): x is TwinState => !!x);
    const tir = available.map((x) => n(x.time_in_range_7d)).filter((x): x is number => x !== null);
    const highHyper = available.filter((x) => x.prediction?.risk_band_hyper === "high").length;
    return { available: available.length, averageTir: tir.length ? tir.reduce((a, b) => a + b, 0) / tir.length : null, highHyper };
  }, [data.twins]);

  
function downloadPdf() {
    if (loading && !data.updatedAt) {
      window.alert("The first refresh is still running. Please wait a moment and try again.");
      return;
    }
    if (!data.updatedAt) {
      window.alert("No report snapshot is available yet. Click Refresh now and try again when it completes.");
      return;
    }
    window.print();
  }

  function exportCsv() {
    const rows: Array<Array<string | number>> = [["MedIntel AI — Live Operations Report"], ["Generated at", data.updatedAt?.toISOString() ?? "not yet refreshed"], [], ["Section", "Metric", "Value", "Context"],
      ["Overview", "Total registered patients", exec?.total_patients ?? "Unavailable", "Executive analytics API"],
      ["Overview", "Currently admitted", exec?.currently_admitted ?? "Unavailable", "Executive analytics API"],
      ["Overview", "Bed capacity", exec?.total_bed_capacity ?? "Unavailable", "Configured hospital capacity"],
      ["Overview", "Occupancy rate", exec ? `${(exec.occupancy_rate * 100).toFixed(1)}%` : "Unavailable", "Executive analytics API"],
      ["Patients", "Directory total", patients?.total ?? "Unavailable", "Patient directory API"],
      ["GlucoTwin", "Synthetic cohort size", gluco?.total ?? "Unavailable", "Synthetic diabetes cohort"],
      ["ICU Risk", "Risk assessments returned", riskSummary.available, "Up to 10 directory records queried; not a full-cohort count"],
      ["ICU Risk", "High-risk results", riskSummary.high, "Only successful sample responses"],
      ["GlucoTwin", "Patients with twin state", twinSummary.available, "Up to 8 cohort records queried"],
      ["GlucoTwin", "Average time in range", twinSummary.averageTir === null ? "Unavailable" : `${(twinSummary.averageTir * 100).toFixed(1)}%`, "Average of returned twin states; scale follows API response"],
      ["GlucoTwin", "High hyperglycaemia-risk states", twinSummary.highHyper, "Only successful sample responses"],
      ...((exec?.top_diagnoses ?? []).map((x) => ["Disease Analytics", x.description, x.count, "Top diagnoses from executive analytics"] as Array<string | number>)),
      ...((exec?.ward_distribution ?? []).map((x) => ["Overview", `Ward: ${x.ward}`, x.count, "Admitted patient distribution"] as Array<string | number>)),
      ...data.errors.map((e) => ["Data quality", "Source unavailable", e, "Partial report"] as Array<string | number>),
    ];
    const csv = rows.map((row) => row.map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n");
    const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `medintel-live-report-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(url);
  }

  const statusLabel = loading ? "CONNECTING" : lastError ? "PARTIAL DATA" : "LIVE SOURCES";
  return <AppLayout title="Reports">
    <div className="-mx-4 -my-6 min-h-[calc(100vh-74px)] bg-slate-50 px-4 py-6 text-slate-800 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 xl:-mx-10 xl:px-10 print:mx-0 print:bg-white print:px-0 print:text-slate-900">
      <div id="reports-content" className="mx-auto max-w-[1500px] space-y-6">
        <div className="relative overflow-hidden rounded-[26px] border border-slate-200 bg-gradient-to-br from-white via-white to-teal-50 p-6 sm:p-9 print:border-slate-200 print:bg-white print:text-slate-900">
          <div className="pointer-events-none absolute -right-10 -top-16 h-64 w-64 rounded-full border border-teal-200/10" /><div className="pointer-events-none absolute -right-1 top-0 h-44 w-44 rounded-full border border-teal-200/10" />
          <div className="relative flex flex-col justify-between gap-7 xl:flex-row xl:items-end">
            <div className="max-w-3xl"><div className="mb-5 inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[.2em] text-teal-700"><span className={`h-1.5 w-1.5 rounded-full ${loading ? "bg-amber-300" : lastError ? "bg-amber-300" : "animate-pulse bg-emerald-300"}`} /> MedIntel Intelligence Brief</div><h1 className="text-3xl font-semibold leading-tight tracking-[-.04em] text-slate-900 sm:text-5xl">Clinical operations,<br className="hidden sm:block" /> in one clear view.</h1><p className="mt-4 max-w-2xl text-sm leading-6 text-slate-600">A live, consolidated report across hospital overview, patient records, ICU risk assessments, GlucoTwin and disease analytics.</p></div>
            <div className="pdf-hide flex flex-wrap gap-2 print:hidden"><button onClick={() => void refresh(true)} disabled={refreshing} className="rounded-xl border border-slate-200 bg-slate-100 px-4 py-3 text-xs font-semibold text-slate-800 transition hover:bg-slate-100 disabled:opacity-50">{refreshing ? "Refreshing…" : "↻ Refresh now"}</button><button onClick={exportCsv} className="rounded-xl bg-teal-700 px-4 py-3 text-xs font-bold text-white transition hover:bg-teal-800">↓ Export CSV</button><button type="button" onClick={() => void downloadPdf()} className="rounded-xl border border-slate-200 bg-slate-100 px-4 py-3 text-xs font-semibold text-slate-800 transition hover:bg-slate-100">↓ Print / Save PDF</button></div>
          </div>
          <div className="relative mt-7 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-slate-200 pt-4 text-[11px] text-slate-500"><span className="inline-flex items-center gap-2"><span className={`h-1.5 w-1.5 rounded-full ${lastError ? "bg-amber-300" : "bg-emerald-300"}`} />{statusLabel}</span><span>Auto-refresh every 30 seconds</span><span>Last updated: {dateTime(data.updatedAt)}</span><span>Reporting window: current snapshot</span></div>
        </div>

        {lastError && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{lastError} {data.errors.length > 0 && <span className="block mt-1 text-xs text-amber-800/70">{data.errors.join(" · ")}</span>}</div>}
        {loading && !data.updatedAt ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[1,2,3,4].map((x)=><div key={x} className="h-32 animate-pulse rounded-2xl border border-slate-200 bg-slate-50" />)}</div> : null}

        <section><div className="mb-4 flex items-end justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-teal-700">01 / Executive pulse</p><h2 className="mt-2 text-xl font-semibold tracking-tight">Hospital at a glance</h2></div><span className="text-[10px] text-slate-500">Source: /api/analytics/executive</span></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Registered patients" value={fmt(exec?.total_patients)} note="Patient records represented in the overview"/><Metric label="Currently admitted" value={fmt(exec?.currently_admitted)} note={`${admittedPercent === null ? "Admission share unavailable" : `${admittedPercent.toFixed(1)}% of registered patients`}`} tone="blue"/><Metric label="Bed occupancy" value={pct(exec?.occupancy_rate)} note={`${fmt(exec?.total_bed_capacity)} configured beds · overview API`} tone={exec && exec.occupancy_rate > .85 ? "amber" : "teal"}/><Metric label="New patients · 7d" value={fmt(exec?.new_patients_last_7_days)} note="Recently created patient records" tone="violet"/></div></section>

        <div className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]"><Section eyebrow="02 / Patient directory" title="Patient record coverage" note="Counts are from the live patient directory; detailed records remain in the Patients tab."><div className="grid grid-cols-2 gap-3"><div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs text-slate-500">Directory total</p><p className="mt-2 text-2xl font-semibold tabular-nums">{fmt(patients?.total)}</p></div><div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs text-slate-500">Returned on this page</p><p className="mt-2 text-2xl font-semibold tabular-nums">{fmt(patients?.items?.length)}</p></div></div><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[440px] text-left text-xs"><thead className="text-[10px] uppercase tracking-[.15em] text-slate-500"><tr><th className="pb-3 font-semibold">Patient</th><th className="pb-3 font-semibold">MRN</th><th className="pb-3 font-semibold">Ward</th><th className="pb-3 font-semibold">Status</th></tr></thead><tbody>{(patients?.items ?? []).slice(0,6).map((p)=><tr key={p.id} className="border-t border-slate-200"><td className="py-3 pr-3 font-medium text-slate-700">{p.first_name} {p.last_name}</td><td className="py-3 pr-3 text-slate-500">{p.mrn}</td><td className="py-3 pr-3 text-slate-500">{p.ward || "Not assigned"}</td><td className="py-3"><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${p.is_admitted ? "bg-teal-50 text-teal-700" : "bg-slate-100 text-slate-500"}`}>{p.is_admitted ? "Admitted" : "Not admitted"}</span></td></tr>)}</tbody></table>{(!patients || patients.items.length === 0) && <p className="py-8 text-center text-sm text-slate-500">No patient records returned by this source.</p>}</div></Section>

        <Section eyebrow="03 / Critical care" title="ICU risk monitor snapshot" note={`Live predictions attempted for up to 10 patients from the directory (${riskSummary.available} responses returned). This is a sample, not a full-cohort census.`}><div className="grid grid-cols-3 gap-3"><div className="rounded-xl border border-rose-200 bg-rose-50 p-4"><p className="text-[10px] uppercase tracking-widest text-rose-700">High</p><p className="mt-2 text-2xl font-semibold text-rose-700">{riskSummary.high}</p></div><div className="rounded-xl border border-amber-200 bg-amber-50 p-4"><p className="text-[10px] uppercase tracking-widest text-amber-700/70">Medium</p><p className="mt-2 text-2xl font-semibold text-amber-700">{riskSummary.medium}</p></div><div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4"><p className="text-[10px] uppercase tracking-widest text-emerald-700/70">Low</p><p className="mt-2 text-2xl font-semibold text-emerald-700">{riskSummary.low}</p></div></div><p className="mt-4 text-xs leading-5 text-slate-500">Failed or unavailable predictions are excluded from these counts. Risk results are experimental decision-support outputs and require clinician interpretation.</p><div className="mt-4 space-y-2">{data.icu.filter((x)=>x.result).slice(0,5).map(({patientId,result})=><div key={patientId} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2.5"><span className="truncate font-mono text-[11px] text-slate-500">{patientId.slice(0,8)}…</span><span className="text-xs text-slate-600">{(result!.probability*100).toFixed(1)}% predicted risk</span><span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase ${result!.risk_level === "high" ? "bg-rose-50 text-rose-700" : result!.risk_level === "medium" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>{result!.risk_level}</span></div>)}</div></Section></div>

        <div className="grid gap-5 xl:grid-cols-2"><Section eyebrow="04 / GlucoTwin" title="Digital twin snapshot" note="Digital twin insights and cohort-level metrics."><div className="grid grid-cols-2 gap-3"><div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs text-slate-500">Cohort size</p><p className="mt-2 text-2xl font-semibold">{fmt(gluco?.total)}</p></div><div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs text-slate-500">Twin states returned</p><p className="mt-2 text-2xl font-semibold">{twinSummary.available} / {data.twins.length}</p></div><div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs text-slate-500">Mean time-in-range</p><p className="mt-2 text-2xl font-semibold">{twinSummary.averageTir === null ? "—" : `${(twinSummary.averageTir <= 1 ? twinSummary.averageTir * 100 : twinSummary.averageTir).toFixed(1)}%`}</p></div><div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs text-slate-500">High hyperglycaemia risk</p><p className="mt-2 text-2xl font-semibold text-amber-700">{twinSummary.highHyper}</p></div></div><div className="mt-5 space-y-2">{data.twins.filter((x)=>x.state).slice(0,5).map(({patientId,state})=><div key={patientId} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-3"><span className="font-mono text-xs text-slate-600">{patientId}</span><span className="text-xs text-slate-500">TIR {state?.time_in_range_7d == null ? "—" : `${(Number(state.time_in_range_7d) <= 1 ? Number(state.time_in_range_7d)*100 : Number(state.time_in_range_7d)).toFixed(1)}%`}</span><span className="text-[10px] font-semibold text-slate-500">{state?.confidence_flag || "unknown confidence"}</span></div>)}</div></Section>

        <Section eyebrow="05 / Disease analytics" title="Diagnoses & ward distribution" note="The same backend summary powers Overview and Disease Analytics; no values are fabricated in this report."><div className="mb-5"><h3 className="mb-3 text-xs font-semibold text-slate-600">Top recorded diagnoses</h3><div className="space-y-3">{(exec?.top_diagnoses ?? []).map((d)=>{const max=Math.max(1,...(exec?.top_diagnoses ?? []).map((x)=>x.count));return <div key={d.description}><div className="mb-1.5 flex justify-between gap-3 text-xs"><span className="truncate text-slate-600">{d.description}</span><span className="tabular-nums text-slate-500">{d.count}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-gradient-to-r from-teal-400 to-cyan-300" style={{width:`${Math.max(0,Math.min(100,d.count/max*100))}%`}} /></div></div>})}{(!exec || exec.top_diagnoses.length===0) && <p className="text-xs text-slate-500">No diagnosis aggregates returned.</p>}</div></div><div className="border-t border-slate-200 pt-5"><h3 className="mb-3 text-xs font-semibold text-slate-600">Admitted patients by ward</h3><div className="space-y-3">{(exec?.ward_distribution ?? []).map((w)=>{const max=Math.max(1,...(exec?.ward_distribution ?? []).map((x)=>x.count));return <div key={w.ward}><div className="mb-1.5 flex justify-between text-xs"><span className="text-slate-600">{w.ward}</span><span className="text-slate-500">{w.count}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-gradient-to-r from-sky-400 to-indigo-300" style={{width:`${Math.max(0,Math.min(100,w.count/max*100))}%`}} /></div></div>})}{(!exec || exec.ward_distribution.length===0) && <p className="text-xs text-slate-500">No ward aggregates returned.</p>}</div></div></Section></div>

        <footer className="flex flex-col justify-between gap-3 border-t border-slate-200 py-5 text-[10px] leading-5 text-slate-500 sm:flex-row"><p>MEDINTEL AI · CONSOLIDATED REPORT · Source values are fetched from the application APIs.</p><p>Prototype only. Not a substitute for professional clinical judgement.</p></footer>
      </div>
    </div>
  </AppLayout>;
}
