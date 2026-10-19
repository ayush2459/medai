import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

type Guidance = {
  patient_id: string; generated_at: string; generated_by: string; disclaimer: string;
  suggested_tests: { test: string; reason: string; timing?: string }[];
  precautions: { title: string; detail: string }[]; red_flags: string[];
  clinical_notes?: string[];
};
type Props = { patientId: string; patientName: string; onClose: () => void };

export function ClinicalGuidanceModal({ patientId, patientName, onClose }: Props) {
  const [data, setData] = useState<Guidance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      let twin: any = {}, prediction: any = {}, investigations: any[] = [];
      let patientRecord: any = {};

      // Load the real patient record first. This directory uses UUIDs;
      // GlucoTwin may use a separate cohort identifier.
      try {
        const patientResponse = await api.get(
          `/api/patients/${encodeURIComponent(patientId)}`
        );
        patientRecord = patientResponse.data ?? {};
      } catch (e) {
        console.warn("Could not load patient details for guidance.");
      }

      const conditions: string[] = [];
      const seenConditions = new Set<string>();

      // Extract only explicitly recorded diagnoses/conditions; do not infer them.
      const diagnosisKeys = new Set([
        "diagnosis", "diagnoses", "condition", "conditions",
        "problem", "problems", "display_name", "icd_description"
      ]);

      function collectConditions(value: any, parentKey = "", depth = 0) {
        if (depth > 7 || value == null) return;

        const key = parentKey.toLowerCase();

        if (Array.isArray(value)) {
          value.forEach(item => collectConditions(item, parentKey, depth + 1));
          return;
        }

        if (typeof value === "string" || typeof value === "number") {
          const text = String(value).trim();
          if (
            text &&
            (diagnosisKeys.has(key) ||
              ["diagnosis", "diagnoses", "condition", "conditions",
               "problem", "problems"].some(k => key.includes(k))) &&
            !seenConditions.has(text)
          ) {
            seenConditions.add(text);
            conditions.push(text);
          }
          return;
        }

        if (typeof value !== "object") return;

        // Diagnosis records commonly store their actual name under "name",
        // "title", or "description", rather than a "diagnosis" field.
        if (
          ["diagnosis", "diagnoses", "condition", "conditions",
           "problem", "problems"].some(k => key.includes(k))
        ) {
          for (const field of ["name", "title", "display", "description",
                               "display_name", "condition_name"]) {
            const candidate = value[field];
            if (typeof candidate === "string" && candidate.trim() &&
                !seenConditions.has(candidate.trim())) {
              seenConditions.add(candidate.trim());
              conditions.push(candidate.trim());
            }
          }
        }

        for (const [childKey, child] of Object.entries(value)) {
          collectConditions(child, childKey, depth + 1);
        }
      }

      collectConditions(patientRecord);

      // Main-directory UUIDs are not assumed to be GlucoTwin cohort IDs.
      const isUuid =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
          .test(patientId);

      if (!isUuid) {
        try {
          const r = await api.get(
            `/api/v1/twin/${encodeURIComponent(patientId)}`
          );
          twin = r.data ?? {};
          prediction = twin.prediction ?? {};
          investigations = Array.isArray(twin.investigations)
            ? twin.investigations : [];
        } catch (e) {
          console.info("GlucoTwin state unavailable for this cohort ID.");
        }

        // A missing wearable record is acceptable; it is not a prediction.
        try {
          const r = await api.get(
            `/api/v1/predict/${encodeURIComponent(patientId)}`
          );
          prediction = r.data ?? prediction;
        } catch (e) {
          console.info("No usable GlucoTwin prediction is available.");
        }

        try {
          const r = await api.get(
            `/api/v1/investigations/${encodeURIComponent(patientId)}`
          );
          if (Array.isArray(r.data?.suggestions)) {
            investigations = r.data.suggestions;
          }
        } catch (e) {
          console.info("GlucoTwin investigations unavailable.");
        }
      }

      if (String(prediction.risk_band_hyper).toLowerCase() === "high")
        conditions.push(
          "High short-term hyperglycaemia risk (model signal, not diagnosis)"
        );
      if (String(prediction.risk_band_hypo).toLowerCase() === "high")
        conditions.push(
          "High short-term hypoglycaemia risk (model signal, not diagnosis)"
        );

      // If the patient record has documented lab results, pass only those
      // records as context. The clinician must decide whether testing is due.
      function collectLabs(value: any, depth = 0) {
        if (depth > 6 || value == null) return;
        if (Array.isArray(value)) {
          value.forEach(item => collectLabs(item, depth + 1));
          return;
        }
        if (typeof value !== "object") return;

        for (const [key, child] of Object.entries(value)) {
          if (
            ["labs", "lab_results", "investigations", "test_results"]
              .includes(key.toLowerCase()) &&
            Array.isArray(child)
          ) {
            for (const item of child) {
              if (item && typeof item === "object") {
                investigations.push({
                  title: String(
                    item.test_name ?? item.name ?? item.test ??
                    item.lab_name ?? "Recorded laboratory result"
                  ),
                  message: "Existing record available for clinician review.",
                  detail: {
                    result: item.result ?? item.value ?? null,
                    date: item.date ?? item.collected_at ?? item.created_at ?? null
                  }
                });
              }
            }
          } else if (child && typeof child === "object") {
            collectLabs(child, depth + 1);
          }
        }
      }

      collectLabs(patientRecord);
      investigations = investigations.filter(
        (item, index, all) =>
          all.findIndex(other =>
            String(other.title ?? other.name ?? other.rule_id ?? "") ===
            String(item.title ?? item.name ?? item.rule_id ?? "")
          ) === index
      );
      const r = await api.post("/api/v1/clinical-guidance", {
        patient_id: patientId,
        conditions,
        prediction,
        investigations,
        patient_context: {
          documented_conditions: Array.isArray(patientRecord.diagnoses)
            ? patientRecord.diagnoses.map((d: any) => ({
                description: d.description ?? d.name ?? d.title ?? "Recorded diagnosis",
                icd_code: d.icd_code ?? null,
                diagnosed_at: d.diagnosed_at ?? null,
                notes: d.notes ?? null
              }))
            : [],
          available_results: Array.isArray(patientRecord.lab_results)
            ? patientRecord.lab_results.map((lab: any) => ({
                test_name: lab.test_name,
                value: lab.value ?? null,
                unit: lab.unit ?? null,
                reference_range: lab.reference_range ?? null,
                is_abnormal: Boolean(lab.is_abnormal),
                collected_at: lab.collected_at ?? null
              }))
            : [],
          current_prescriptions: Array.isArray(patientRecord.prescriptions)
            ? patientRecord.prescriptions.map((p: any) => ({
                medication_name: p.medication_name,
                frequency: p.frequency,
                start_date: p.start_date ?? null,
                end_date: p.end_date ?? null
              }))
            : [],
          doctor_notes: Array.isArray(patientRecord.notes)
            ? patientRecord.notes.map((n: any) => ({
                content: n.content,
                created_at: n.created_at ?? null
              }))
            : [],
          glucose_prediction_available: Boolean(
            prediction && (
              prediction.p_hyper_120 != null ||
              prediction.p_hypo_120 != null ||
              prediction.risk_band_hyper ||
              prediction.risk_band_hypo
            )
          )
        }
      });
      setData(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || "Could not load guidance.");
    } finally { setLoading(false); }
  }, [patientId]);

  useEffect(() => { void load(); }, [load]);

  return <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/40 p-3 sm:p-6"
    role="dialog" aria-modal="true" aria-labelledby="guidance-title">
    <section className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
      <header className="sticky top-0 flex items-start justify-between border-b bg-white p-5">
        <div><p className="text-xs font-bold uppercase tracking-wider text-teal-700">Patient decision support</p>
          <h2 id="guidance-title" className="mt-1 text-xl font-bold text-slate-800">Tests &amp; Care Guidance</h2>
          <p className="text-sm text-slate-500">{patientName} · {patientId}</p></div>
        <button onClick={onClose} className="rounded-lg border px-3 py-2 text-sm">Close ✕</button>
      </header>
      <div className="p-5 sm:p-6">
        <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <strong>Clinician review required.</strong> This prototype does not diagnose all diseases or prescribe treatment.
          Do not change medication or delay emergency care based on AI output.
        </div>
        {loading && <p className="py-8 text-center text-slate-500">Loading current model results and guidance…</p>}
        {error && <p role="alert" className="mb-4 rounded bg-red-50 p-3 text-sm text-red-700">{error}
          <button onClick={() => void load()} className="ml-3 underline">Retry</button></p>}
        {data && !loading && <>
          <div className="mb-5 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
            <span>Source: <strong>{data.generated_by}</strong></span>
            <span>Updated {new Date(data.generated_at).toLocaleString()}</span>
            <button onClick={() => void load()} className="rounded-lg border border-teal-200 px-3 py-2 font-semibold text-teal-800">Refresh guidance</button>
          </div>
          <h3 className="mb-3 text-lg font-bold">Tests to discuss with the doctor</h3>
          <div className="mb-6 grid gap-3 md:grid-cols-2">{data.suggested_tests.map((x, i) =>
            <article key={x.test + i} className="rounded-xl border p-4">
              <h4 className="font-semibold">{x.test}</h4><p className="mt-2 text-sm text-slate-600">{x.reason}</p>
              {x.timing && <p className="mt-2 text-xs text-slate-500">Timing: {x.timing}</p>}
            </article>)}</div>
          <h3 className="mb-3 text-lg font-bold">Precautions and care discussion</h3>
          <div className="mb-6 grid gap-3 md:grid-cols-2">{data.precautions.map((x, i) =>
            <article key={x.title + i} className="rounded-xl bg-teal-50 p-4">
              <h4 className="font-semibold text-teal-900">{x.title}</h4><p className="mt-2 text-sm text-teal-900/80">{x.detail}</p>
            </article>)}</div>
          <h3 className="mb-3 text-lg font-bold">Warning signs</h3>
          <ul className="list-disc space-y-2 pl-5 text-sm">{data.red_flags.map((x, i) => <li key={i}>{x}</li>)}</ul>
          {Array.isArray(data.clinical_notes) && data.clinical_notes.length > 0 ? <ul className="mt-4 list-disc pl-5 text-sm">{data.clinical_notes.map((x, i) => <li key={i}>{String(x)}</li>)}</ul> : null}
          <p className="mt-6 border-t pt-4 text-xs text-slate-500">{data.disclaimer}</p>
        </>}
      </div>
    </section>
  </div>;
}
