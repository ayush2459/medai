import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AppLayout } from "../components/AppLayout";
import { api } from "../lib/api";
import type { ExecutiveSummary, PaginatedPatients, GlucoPatient, TwinState, IcuRiskResponse } from "../lib/types";
import { jsPDF } from "jspdf";

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
  const tones = { teal: "border-teal-300/20 bg-teal-300/[0.07] text-teal-200", blue: "border-sky-300/20 bg-sky-300/[0.07] text-sky-200", amber: "border-amber-300/20 bg-amber-300/[0.07] text-amber-200", violet: "border-violet-300/20 bg-violet-300/[0.07] text-violet-200" };
  return <div className={`rounded-2xl border p-5 ${tones[tone]}`}><p className="text-[10px] font-bold uppercase tracking-[.19em] opacity-75">{label}</p><p className="mt-3 text-3xl font-semibold tracking-tight text-white tabular-nums">{value}</p><p className="mt-2 text-xs leading-5 text-slate-400">{note}</p></div>;
}

function Section({ eyebrow, title, note, children }: { eyebrow: string; title: string; note?: string; children: ReactNode }) {
  return <section className="rounded-2xl border border-white/[0.09] bg-[#111b2b]/90 p-5 shadow-[0_18px_55px_rgba(0,0,0,.18)] sm:p-6"><div className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-teal-300">{eyebrow}</p><h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-100">{title}</h2>{note && <p className="mt-1 text-xs leading-5 text-slate-400">{note}</p>}</div></div>{children}</section>;
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

  
async function downloadPdf() {
    if (loading && !data.updatedAt) {
      window.alert("The first refresh is still running. Please wait a moment and try again.");
      return;
    }
    if (!data.updatedAt) {
      window.alert("No report snapshot is available yet. Click Refresh now and try again when it completes.");
      return;
    }

    try {
      // Build a true text-based PDF. This avoids html2canvas parsing Tailwind's
      // modern oklab()/oklch() colors and prevents desktop layouts being clipped.
      const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = 16;
      const contentWidth = pageWidth - margin * 2;
      let y = 18;
      let page = 1;

      const colors = {
        ink: [25, 36, 53] as [number, number, number],
        muted: [91, 105, 123] as [number, number, number],
        teal: [13, 116, 112] as [number, number, number],
        line: [220, 226, 233] as [number, number, number],
        pale: [242, 247, 248] as [number, number, number],
      };

      const ensureSpace = (height: number) => {
        if (y + height > pageHeight - 18) {
          doc.addPage();
          page += 1;
          y = 18;
        }
      };

      const textLines = (text: string, fontSize = 9, color = colors.ink, indent = 0) => {
        doc.setFontSize(fontSize);
        doc.setTextColor(...color);
        const lines = doc.splitTextToSize(text || "—", contentWidth - indent) as string[];
        const lineHeight = fontSize * 0.48;
        ensureSpace(lines.length * lineHeight + 2);
        doc.text(lines, margin + indent, y);
        y += lines.length * lineHeight + 2;
      };

      const section = (title: string, note?: string) => {
        ensureSpace(14);
        y += 3;
        doc.setFillColor(...colors.pale);
        doc.roundedRect(margin, y - 5, contentWidth, 9, 2, 2, "F");
        doc.setFont("helvetica", "bold");
        doc.setFontSize(10);
        doc.setTextColor(...colors.teal);
        doc.text(title, margin + 3, y + 1);
        y += 9;
        if (note) textLines(note, 8, colors.muted);
      };

      const metric = (label: string, value: string, note?: string) => {
        ensureSpace(note ? 13 : 8);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(8);
        doc.setTextColor(...colors.muted);
        doc.text(label.toUpperCase(), margin + 2, y);
        doc.setFontSize(13);
        doc.setTextColor(...colors.ink);
        doc.text(value || "—", margin + 2, y + 5.5);
        y += 9;
        if (note) {
          doc.setFont("helvetica", "normal");
          doc.setFontSize(7.5);
          doc.setTextColor(...colors.muted);
          const lines = doc.splitTextToSize(note, contentWidth - 4) as string[];
          ensureSpace(lines.length * 3.8);
          doc.text(lines, margin + 2, y);
          y += lines.length * 3.8 + 2;
        }
        doc.setDrawColor(...colors.line);
        doc.line(margin, y, pageWidth - margin, y);
        y += 3;
      };

      const row = (label: string, value: string) => {
        const valueLines = doc.splitTextToSize(value || "—", contentWidth * 0.62) as string[];
        const height = Math.max(5, valueLines.length * 4.1);
        ensureSpace(height + 2);
        doc.setFont("helvetica", "normal");
        doc.setFontSize(8.5);
        doc.setTextColor(...colors.muted);
        doc.text(doc.splitTextToSize(label, contentWidth * 0.32) as string[], margin + 1, y);
        doc.setTextColor(...colors.ink);
        doc.text(valueLines, margin + contentWidth * 0.36, y);
        y += height + 2;
        doc.setDrawColor(...colors.line);
        doc.line(margin, y - 1, pageWidth - margin, y - 1);
      };

      // Cover header
      doc.setFillColor(11, 24, 39);
      doc.roundedRect(margin, y - 7, contentWidth, 35, 3, 3, "F");
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8);
      doc.setTextColor(111, 220, 207);
      doc.text("MEDINTEL AI  /  INTELLIGENCE BRIEF", margin + 5, y);
      doc.setFontSize(19);
      doc.setTextColor(255, 255, 255);
      doc.text("Clinical operations report", margin + 5, y + 9);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(8.5);
      doc.setTextColor(226, 233, 241);
      doc.text("Consolidated snapshot across hospital overview, patient records, ICU risk, GlucoTwin and disease analytics.", margin + 5, y + 16, { maxWidth: contentWidth - 10 });
      doc.setFontSize(7.5);
      doc.text(`Generated: ${new Date().toLocaleString()}   |   Data refreshed: ${data.updatedAt.toLocaleString()}`, margin + 5, y + 23, { maxWidth: contentWidth - 10 });
      y += 35;

      if (lastError) {
        textLines(`DATA QUALITY NOTICE: ${lastError} ${data.errors.join(" ")}`, 8, [153, 83, 14]);
      } else {
        textLines("Source status: live API responses received. Values below reflect the latest successful refresh.", 8, colors.muted);
      }

      section("01 / EXECUTIVE PULSE", "Source: executive analytics API");
      metric("Registered patients", fmt(exec?.total_patients), "Patient records represented in the overview.");
      metric("Currently admitted", fmt(exec?.currently_admitted), admittedPercent === null ? "Admission share unavailable." : `${admittedPercent.toFixed(1)}% of registered patients.`);
      metric("Bed occupancy", pct(exec?.occupancy_rate), `${fmt(exec?.total_bed_capacity)} configured beds.`);
      metric("New patients · 7 days", fmt(exec?.new_patients_last_7_days), "Recently created patient records.");

      section("02 / PATIENT DIRECTORY", "Directory counts come from the patient API; only the first six records are included here.");
      row("Directory total", fmt(patients?.total));
      row("Records returned on page", fmt(patients?.items?.length));
      const patientRows = (patients?.items ?? []).slice(0, 6);
      if (!patientRows.length) textLines("No patient records returned by this source.", 8, colors.muted);
      patientRows.forEach((p, index) => row(`Patient ${index + 1}`, `${p.first_name} ${p.last_name} | MRN: ${p.mrn} | Ward: ${p.ward || "Not assigned"} | ${p.is_admitted ? "Admitted" : "Not admitted"}`));

      section("03 / CRITICAL CARE", `ICU predictions attempted for up to 10 directory records; ${riskSummary.available} responses returned. This is a sample, not a full-cohort census.`);
      row("High-risk results", String(riskSummary.high));
      row("Medium-risk results", String(riskSummary.medium));
      row("Low-risk results", String(riskSummary.low));
      row("Successful predictions", String(riskSummary.available));
      data.icu.filter((x) => x.result).slice(0, 10).forEach(({ patientId, result }) => {
        row(`Patient ${patientId.slice(0, 8)}…`, `${(result!.probability * 100).toFixed(1)}% predicted risk | ${result!.risk_level.toUpperCase()}`);
      });
      textLines("Clinical caution: risk outputs are experimental decision-support results and require clinician interpretation.", 7.5, colors.muted);

      section("04 / GLUCOTWIN", "Synthetic diabetes cohort. Prototype data is not for clinical use.");
      row("Cohort size", fmt(gluco?.total));
      row("Twin states returned", `${twinSummary.available} / ${data.twins.length}`);
      row("Mean time-in-range", twinSummary.averageTir === null ? "Unavailable" : `${(twinSummary.averageTir <= 1 ? twinSummary.averageTir * 100 : twinSummary.averageTir).toFixed(1)}%`);
      row("High hyperglycaemia-risk states", String(twinSummary.highHyper));
      data.twins.filter((x) => x.state).slice(0, 8).forEach(({ patientId, state }) => {
        const tir = state?.time_in_range_7d;
        row(patientId, `Time in range: ${tir == null ? "—" : `${(Number(tir) <= 1 ? Number(tir) * 100 : Number(tir)).toFixed(1)}%`} | Confidence: ${state?.confidence_flag || "unknown"}`);
      });

      section("05 / DISEASE ANALYTICS", "Aggregates returned by the executive analytics API.");
      textLines("Top recorded diagnoses", 8.5, colors.ink);
      if (exec?.top_diagnoses?.length) {
        exec.top_diagnoses.forEach((d) => row(d.description, String(d.count)));
      } else {
        textLines("No diagnosis aggregates returned.", 8, colors.muted);
      }
      y += 2;
      textLines("Admitted patients by ward", 8.5, colors.ink);
      if (exec?.ward_distribution?.length) {
        exec.ward_distribution.forEach((w) => row(w.ward, String(w.count)));
      } else {
        textLines("No ward aggregates returned.", 8, colors.muted);
      }

      if (data.errors.length) {
        section("DATA SOURCE NOTES");
        data.errors.forEach((error) => textLines(`• ${error}`, 8, [153, 83, 14]));
      }

      // Consistent footer and page numbering on every page.
      const pageCount = doc.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setDrawColor(...colors.line);
        doc.line(margin, pageHeight - 12, pageWidth - margin, pageHeight - 12);
        doc.setFont("helvetica", "normal");
        doc.setFontSize(7);
        doc.setTextColor(...colors.muted);
        doc.text("MEDINTEL AI · Consolidated report · Prototype only; not a substitute for professional clinical judgement.", margin, pageHeight - 7, { maxWidth: contentWidth - 20 });
        doc.text(`${i} / ${pageCount}`, pageWidth - margin, pageHeight - 7, { align: "right" });
      }

      doc.save(`MedIntel_Report_${new Date().toISOString().slice(0, 10)}.pdf`);
    } catch (error) {
      console.error("MedIntel PDF generation failed:", error);
      const details = error instanceof Error ? error.message : String(error);
      window.alert(`PDF generation failed: ${details}`);
    }
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
      ["GlucoTwin", "Patients with twin state", twinSummary.available, "Up to 8 synthetic cohort records queried"],
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
    <div className="-mx-4 -my-6 min-h-[calc(100vh-74px)] bg-[#080e19] px-4 py-6 text-slate-100 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 xl:-mx-10 xl:px-10 print:mx-0 print:bg-white print:px-0 print:text-slate-900">
      <div id="reports-content" className="mx-auto max-w-[1500px] space-y-6">
        <div className="relative overflow-hidden rounded-[26px] border border-white/10 bg-[radial-gradient(ellipse_at_80%_0%,rgba(13,148,136,.28),transparent_42%),linear-gradient(120deg,#111c2c,#0b1422_60%,#102c36)] p-6 sm:p-9 print:border-slate-200 print:bg-white print:text-slate-900">
          <div className="pointer-events-none absolute -right-10 -top-16 h-64 w-64 rounded-full border border-teal-200/10" /><div className="pointer-events-none absolute -right-1 top-0 h-44 w-44 rounded-full border border-teal-200/10" />
          <div className="relative flex flex-col justify-between gap-7 xl:flex-row xl:items-end">
            <div className="max-w-3xl"><div className="mb-5 inline-flex items-center gap-2 rounded-full border border-teal-200/20 bg-teal-300/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[.2em] text-teal-200"><span className={`h-1.5 w-1.5 rounded-full ${loading ? "bg-amber-300" : lastError ? "bg-amber-300" : "animate-pulse bg-emerald-300"}`} /> MedIntel Intelligence Brief</div><h1 className="text-3xl font-semibold leading-tight tracking-[-.04em] text-white sm:text-5xl">Clinical operations,<br className="hidden sm:block" /> in one clear view.</h1><p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300">A live, consolidated report across hospital overview, patient records, ICU risk assessments, GlucoTwin and disease analytics.</p></div>
            <div className="pdf-hide flex flex-wrap gap-2 print:hidden"><button onClick={() => void refresh(true)} disabled={refreshing} className="rounded-xl border border-white/15 bg-white/[0.06] px-4 py-3 text-xs font-semibold text-slate-100 transition hover:bg-white/10 disabled:opacity-50">{refreshing ? "Refreshing…" : "↻ Refresh now"}</button><button onClick={exportCsv} className="rounded-xl bg-teal-300 px-4 py-3 text-xs font-bold text-[#06252a] transition hover:bg-teal-200">↓ Export CSV</button><button type="button" onClick={() => void downloadPdf()} className="rounded-xl border border-white/15 bg-white/[0.06] px-4 py-3 text-xs font-semibold text-slate-100 transition hover:bg-white/10">↓ Download PDF</button></div>
          </div>
          <div className="relative mt-7 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/10 pt-4 text-[11px] text-slate-400"><span className="inline-flex items-center gap-2"><span className={`h-1.5 w-1.5 rounded-full ${lastError ? "bg-amber-300" : "bg-emerald-300"}`} />{statusLabel}</span><span>Auto-refresh every 30 seconds</span><span>Last updated: {dateTime(data.updatedAt)}</span><span>Reporting window: current snapshot</span></div>
        </div>

        {lastError && <div className="rounded-xl border border-amber-300/20 bg-amber-300/[0.07] p-4 text-sm text-amber-100">{lastError} {data.errors.length > 0 && <span className="block mt-1 text-xs text-amber-100/70">{data.errors.join(" · ")}</span>}</div>}
        {loading && !data.updatedAt ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[1,2,3,4].map((x)=><div key={x} className="h-32 animate-pulse rounded-2xl border border-white/10 bg-white/[0.03]" />)}</div> : null}

        <section><div className="mb-4 flex items-end justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-teal-300">01 / Executive pulse</p><h2 className="mt-2 text-xl font-semibold tracking-tight">Hospital at a glance</h2></div><span className="text-[10px] text-slate-500">Source: /api/analytics/executive</span></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Registered patients" value={fmt(exec?.total_patients)} note="Patient records represented in the overview"/><Metric label="Currently admitted" value={fmt(exec?.currently_admitted)} note={`${admittedPercent === null ? "Admission share unavailable" : `${admittedPercent.toFixed(1)}% of registered patients`}`} tone="blue"/><Metric label="Bed occupancy" value={pct(exec?.occupancy_rate)} note={`${fmt(exec?.total_bed_capacity)} configured beds · overview API`} tone={exec && exec.occupancy_rate > .85 ? "amber" : "teal"}/><Metric label="New patients · 7d" value={fmt(exec?.new_patients_last_7_days)} note="Recently created patient records" tone="violet"/></div></section>

        <div className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]"><Section eyebrow="02 / Patient directory" title="Patient record coverage" note="Counts are from the live patient directory; detailed records remain in the Patients tab."><div className="grid grid-cols-2 gap-3"><div className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4"><p className="text-xs text-slate-400">Directory total</p><p className="mt-2 text-2xl font-semibold tabular-nums">{fmt(patients?.total)}</p></div><div className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4"><p className="text-xs text-slate-400">Returned on this page</p><p className="mt-2 text-2xl font-semibold tabular-nums">{fmt(patients?.items?.length)}</p></div></div><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[440px] text-left text-xs"><thead className="text-[10px] uppercase tracking-[.15em] text-slate-500"><tr><th className="pb-3 font-semibold">Patient</th><th className="pb-3 font-semibold">MRN</th><th className="pb-3 font-semibold">Ward</th><th className="pb-3 font-semibold">Status</th></tr></thead><tbody>{(patients?.items ?? []).slice(0,6).map((p)=><tr key={p.id} className="border-t border-white/[0.06]"><td className="py-3 pr-3 font-medium text-slate-200">{p.first_name} {p.last_name}</td><td className="py-3 pr-3 text-slate-400">{p.mrn}</td><td className="py-3 pr-3 text-slate-400">{p.ward || "Not assigned"}</td><td className="py-3"><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${p.is_admitted ? "bg-teal-300/10 text-teal-200" : "bg-white/[0.06] text-slate-400"}`}>{p.is_admitted ? "Admitted" : "Not admitted"}</span></td></tr>)}</tbody></table>{(!patients || patients.items.length === 0) && <p className="py-8 text-center text-sm text-slate-500">No patient records returned by this source.</p>}</div></Section>

        <Section eyebrow="03 / Critical care" title="ICU risk monitor snapshot" note={`Live predictions attempted for up to 10 patients from the directory (${riskSummary.available} responses returned). This is a sample, not a full-cohort census.`}><div className="grid grid-cols-3 gap-3"><div className="rounded-xl border border-rose-300/15 bg-rose-300/[0.06] p-4"><p className="text-[10px] uppercase tracking-widest text-rose-200/70">High</p><p className="mt-2 text-2xl font-semibold text-rose-200">{riskSummary.high}</p></div><div className="rounded-xl border border-amber-300/15 bg-amber-300/[0.06] p-4"><p className="text-[10px] uppercase tracking-widest text-amber-200/70">Medium</p><p className="mt-2 text-2xl font-semibold text-amber-200">{riskSummary.medium}</p></div><div className="rounded-xl border border-emerald-300/15 bg-emerald-300/[0.06] p-4"><p className="text-[10px] uppercase tracking-widest text-emerald-200/70">Low</p><p className="mt-2 text-2xl font-semibold text-emerald-200">{riskSummary.low}</p></div></div><p className="mt-4 text-xs leading-5 text-slate-500">Failed or unavailable predictions are excluded from these counts. Risk results are experimental decision-support outputs and require clinician interpretation.</p><div className="mt-4 space-y-2">{data.icu.filter((x)=>x.result).slice(0,5).map(({patientId,result})=><div key={patientId} className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] px-3 py-2.5"><span className="truncate font-mono text-[11px] text-slate-400">{patientId.slice(0,8)}…</span><span className="text-xs text-slate-300">{(result!.probability*100).toFixed(1)}% predicted risk</span><span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase ${result!.risk_level === "high" ? "bg-rose-300/10 text-rose-200" : result!.risk_level === "medium" ? "bg-amber-300/10 text-amber-200" : "bg-emerald-300/10 text-emerald-200"}`}>{result!.risk_level}</span></div>)}</div></Section></div>

        <div className="grid gap-5 xl:grid-cols-2"><Section eyebrow="04 / GlucoTwin" title="Digital twin snapshot" note="Uses the synthetic diabetes cohort and returned twin states. Synthetic prototype data is not for clinical use."><div className="grid grid-cols-2 gap-3"><div className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4"><p className="text-xs text-slate-400">Cohort size</p><p className="mt-2 text-2xl font-semibold">{fmt(gluco?.total)}</p></div><div className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4"><p className="text-xs text-slate-400">Twin states returned</p><p className="mt-2 text-2xl font-semibold">{twinSummary.available} / {data.twins.length}</p></div><div className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4"><p className="text-xs text-slate-400">Mean time-in-range</p><p className="mt-2 text-2xl font-semibold">{twinSummary.averageTir === null ? "—" : `${(twinSummary.averageTir <= 1 ? twinSummary.averageTir * 100 : twinSummary.averageTir).toFixed(1)}%`}</p></div><div className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4"><p className="text-xs text-slate-400">High hyperglycaemia risk</p><p className="mt-2 text-2xl font-semibold text-amber-200">{twinSummary.highHyper}</p></div></div><div className="mt-5 space-y-2">{data.twins.filter((x)=>x.state).slice(0,5).map(({patientId,state})=><div key={patientId} className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] px-3 py-3"><span className="font-mono text-xs text-slate-300">{patientId}</span><span className="text-xs text-slate-400">TIR {state?.time_in_range_7d == null ? "—" : `${(Number(state.time_in_range_7d) <= 1 ? Number(state.time_in_range_7d)*100 : Number(state.time_in_range_7d)).toFixed(1)}%`}</span><span className="text-[10px] font-semibold text-slate-400">{state?.confidence_flag || "unknown confidence"}</span></div>)}</div></Section>

        <Section eyebrow="05 / Disease analytics" title="Diagnoses & ward distribution" note="The same backend summary powers Overview and Disease Analytics; no values are fabricated in this report."><div className="mb-5"><h3 className="mb-3 text-xs font-semibold text-slate-300">Top recorded diagnoses</h3><div className="space-y-3">{(exec?.top_diagnoses ?? []).map((d)=>{const max=Math.max(1,...(exec?.top_diagnoses ?? []).map((x)=>x.count));return <div key={d.description}><div className="mb-1.5 flex justify-between gap-3 text-xs"><span className="truncate text-slate-300">{d.description}</span><span className="tabular-nums text-slate-400">{d.count}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]"><div className="h-full rounded-full bg-gradient-to-r from-teal-400 to-cyan-300" style={{width:`${Math.max(0,Math.min(100,d.count/max*100))}%`}} /></div></div>})}{(!exec || exec.top_diagnoses.length===0) && <p className="text-xs text-slate-500">No diagnosis aggregates returned.</p>}</div></div><div className="border-t border-white/[0.08] pt-5"><h3 className="mb-3 text-xs font-semibold text-slate-300">Admitted patients by ward</h3><div className="space-y-3">{(exec?.ward_distribution ?? []).map((w)=>{const max=Math.max(1,...(exec?.ward_distribution ?? []).map((x)=>x.count));return <div key={w.ward}><div className="mb-1.5 flex justify-between text-xs"><span className="text-slate-300">{w.ward}</span><span className="text-slate-400">{w.count}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]"><div className="h-full rounded-full bg-gradient-to-r from-sky-400 to-indigo-300" style={{width:`${Math.max(0,Math.min(100,w.count/max*100))}%`}} /></div></div>})}{(!exec || exec.ward_distribution.length===0) && <p className="text-xs text-slate-500">No ward aggregates returned.</p>}</div></div></Section></div>

        <footer className="flex flex-col justify-between gap-3 border-t border-white/[0.08] py-5 text-[10px] leading-5 text-slate-500 sm:flex-row"><p>MEDINTEL AI · CONSOLIDATED REPORT · Source values are fetched from the application APIs.</p><p>Prototype only. Not a substitute for professional clinical judgement.</p></footer>
      </div>
    </div>
  </AppLayout>;
}
