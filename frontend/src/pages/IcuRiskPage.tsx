import { useEffect, useState } from "react";
import { AppLayout } from "../components/AppLayout";
import { api } from "../lib/api";
import type { IcuRiskResponse, PaginatedPatients, PatientSummary } from "../lib/types";

const RISK_STYLES: Record<string, { border: string; badgeBg: string; badgeText: string; label: string }> = {
  low: { border: "border-l-success", badgeBg: "bg-success/10", badgeText: "text-success", label: "Low risk" },
  medium: { border: "border-l-accent", badgeBg: "bg-accent-soft", badgeText: "text-accent", label: "Medium risk" },
  high: { border: "border-l-danger", badgeBg: "bg-danger-soft", badgeText: "text-danger", label: "High risk" },
};

const FACTOR_LABELS: Record<string, string> = {
  age: "Age",
  gender_male: "Gender (male)",
  gender_female: "Gender (female)",
  heart_rate_bpm: "Heart rate",
  systolic_bp: "Systolic blood pressure",
  diastolic_bp: "Diastolic blood pressure",
  respiratory_rate: "Respiratory rate",
  temperature_c: "Temperature",
  spo2_percent: "Blood oxygen (SpO2)",
  diagnosis_count: "Number of diagnoses",
  abnormal_lab_count: "Abnormal lab results",
  prior_admission_count: "Prior admissions",
};

export function IcuRiskPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PatientSummary[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [selectedPatient, setSelectedPatient] = useState<PatientSummary | null>(null);
  const [risk, setRisk] = useState<IcuRiskResponse | null>(null);
  const [isLoadingRisk, setIsLoadingRisk] = useState(false);
  const [riskError, setRiskError] = useState<string | null>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    const handle = setTimeout(() => {
      setIsSearching(true);
      setSearchError(null);
      api
        .get<PaginatedPatients>("/api/patients", { params: { search: query, page: 1, page_size: 8 } })
        .then((res) => setResults(res.data.items))
        .catch(() => setSearchError("Could not search patients."))
        .finally(() => setIsSearching(false));
    }, 300);
    return () => clearTimeout(handle);
  }, [query]);

  function selectPatient(patient: PatientSummary) {
    setSelectedPatient(patient);
    setResults([]);
    setQuery("");
    setRisk(null);
    setRiskError(null);
    setIsLoadingRisk(true);

    api
      .get<IcuRiskResponse>(`/api/ml/icu-risk/${patient.id}`)
      .then((res) => setRisk(res.data))
      .catch((err) => {
        if (err.response?.status === 403) {
          setRiskError("Your role isn't permitted to view ICU risk scores.");
        } else if (err.response?.status === 503) {
          setRiskError("The ICU risk model hasn't been trained yet on this server.");
        } else {
          setRiskError("Could not load a risk score for this patient.");
        }
      })
      .finally(() => setIsLoadingRisk(false));
  }

  const style = risk ? RISK_STYLES[risk.risk_level] : null;

  return (
    <AppLayout title="ICU Risk Check">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6 rounded-xl border border-border bg-surface p-4 shadow-sm">
          <label className="mb-1 block text-sm font-medium text-ink" htmlFor="patient-search">
            Search for a patient
          </label>
          <input
            id="patient-search"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or MRN…"
            className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
          />

          {isSearching && <p className="mt-2 text-xs text-ink-muted">Searching…</p>}
          {searchError && <p className="mt-2 text-xs text-danger">{searchError}</p>}

          {results.length > 0 && (
            <ul className="mt-3 divide-y divide-border overflow-hidden rounded-lg border border-border">
              {results.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => selectPatient(p)}
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-bg"
                  >
                    <span className="text-ink">
                      {p.first_name} {p.last_name}
                    </span>
                    <span className="tabular-figures text-xs text-ink-muted">{p.mrn}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {selectedPatient && (
          <div className="rounded-xl border border-border bg-surface p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-ink">
                  {selectedPatient.first_name} {selectedPatient.last_name}
                </div>
                <div className="tabular-figures text-xs text-ink-muted">
                  MRN {selectedPatient.mrn} · DOB {selectedPatient.date_of_birth}
                </div>
              </div>
              {selectedPatient.is_admitted && (
                <span className="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-medium text-primary-dark">
                  Admitted{selectedPatient.ward ? ` · ${selectedPatient.ward}` : ""}
                </span>
              )}
            </div>

            {isLoadingRisk && <p className="text-sm text-ink-muted">Calculating risk…</p>}
            {riskError && (
              <div className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{riskError}</div>
            )}

            {risk && style && (
              <div className={`rounded-lg border border-border border-l-4 ${style.border} p-4`}>
                <div className="flex items-baseline justify-between">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${style.badgeBg} ${style.badgeText}`}
                  >
                    {style.label}
                  </span>
                  <span className="tabular-figures text-2xl font-semibold text-ink">
                    {(risk.probability * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="mt-3 text-xs font-medium uppercase tracking-wide text-ink-muted">
                  Top contributing factors
                </div>
                <ul className="mt-1 space-y-1">
                  {risk.top_factors.map((factor) => (
                    <li key={factor} className="text-sm text-ink">
                      {FACTOR_LABELS[factor] ?? factor}
                    </li>
                  ))}
                </ul>

                <p className="mt-4 border-t border-border pt-3 text-xs text-ink-muted">{risk.model_note}</p>
              </div>
            )}
          </div>
        )}

        {!selectedPatient && (
          <p className="text-center text-sm text-ink-muted">
            Search for a patient above to see their ICU admission risk.
          </p>
        )}
      </div>
    </AppLayout>
  );
}
