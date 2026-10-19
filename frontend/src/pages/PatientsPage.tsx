import { useEffect, useState } from "react";
import { AppLayout } from "../components/AppLayout";
import { AddPatientModal } from "../components/AddPatientModal";
import { ClinicalGuidanceModal } from "../components/ClinicalGuidanceModal";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { PaginatedPatients, PatientSummary } from "../lib/types";

const PAGE_SIZE = 10;

const GENDER_LABELS: Record<string, string> = {
  male: "Male",
  female: "Female",
  other: "Other",
};

function calculateAge(dob: string): number {
  const birth = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();

  if (
    today.getMonth() < birth.getMonth() ||
    (today.getMonth() === birth.getMonth() &&
      today.getDate() < birth.getDate())
  ) {
    age--;
  }

  return age;
}

function PatientAvatar({ patient }: { patient: PatientSummary }) {
  const initials = `${patient.first_name?.[0] ?? ""}${patient.last_name?.[0] ?? ""}`.toUpperCase();

  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#e2f4f2] text-sm font-bold text-[#087f8c]">
      {initials || "P"}
    </div>
  );
}

export function PatientsPage() {
  const { user } = useAuth();
  const canAddPatients =
    user?.role === "admin" ||
    user?.role === "doctor" ||
    user?.role === "nurse";

  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPatients | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [guidancePatient, setGuidancePatient] = useState<PatientSummary | null>(null);

  async function loadPatients() {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.get<PaginatedPatients>("/api/patients", {
        params: {
          search: query.trim() || undefined,
          page,
          page_size: PAGE_SIZE,
        },
      });
      setData(response.data);
    } catch {
      setError("We couldn't load the patient directory. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadPatients();
    }, query.trim() ? 300 : 0);

    return () => window.clearTimeout(timer);
  }, [query, page]);

  function handleSearch(value: string) {
    setQuery(value);
    setPage(1);
  }

  function handlePatientCreated() {
    setShowAddModal(false);
    setPage(1);
    setQuery("");
    void loadPatients();
  }

  const totalPages = data
    ? Math.max(1, Math.ceil(data.total / PAGE_SIZE))
    : 1;

  return (
    <AppLayout title="Patients">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-[#087f8c]">
            <span className="h-2 w-2 rounded-full bg-[#20a58b]" />
            PATIENT DIRECTORY
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-[#193342]">
            Patient records
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-[#738391]">
            Find patient records and review their current admission status.
          </p>
        </div>

        {canAddPatients && (
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-[#087f8c] px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#06616b]"
          >
            <span className="text-lg leading-none">+</span>
            Add patient
          </button>
        )}
      </div>

      <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-[#e3eaf0] bg-white p-4">
          <p className="text-xs font-medium text-[#738391]">Records found</p>
          <p className="mt-2 text-2xl font-bold text-[#193342]">
            {data ? data.total.toLocaleString() : "—"}
          </p>
          <p className="mt-1 text-xs text-[#91a0a9]">Matching your search</p>
        </div>

        <div className="rounded-2xl border border-[#e3eaf0] bg-white p-4">
          <p className="text-xs font-medium text-[#738391]">Current page</p>
          <p className="mt-2 text-2xl font-bold text-[#193342]">
            {data ? `${page} / ${totalPages}` : "—"}
          </p>
          <p className="mt-1 text-xs text-[#91a0a9]">
            {PAGE_SIZE} records per page maximum
          </p>
        </div>

        <div className="rounded-2xl border border-[#e3eaf0] bg-white p-4">
          <p className="text-xs font-medium text-[#738391]">Directory status</p>
          <div className="mt-3 flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                error ? "bg-[#cf5c60]" : isLoading ? "bg-[#d99a42]" : "bg-[#319a77]"
              }`}
            />
            <span className="text-sm font-semibold text-[#193342]">
              {error ? "Needs attention" : isLoading ? "Loading records" : "Connected"}
            </span>
          </div>
          <p className="mt-1 text-xs text-[#91a0a9]">
            Live response from the patient API
          </p>
        </div>
      </div>

      <section className="overflow-hidden rounded-2xl border border-[#e3eaf0] bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-[#e8eef2] p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="font-bold text-[#193342]">All patients</h3>
            <p className="mt-1 text-xs text-[#8797a1]">
              Search by the terms supported by your patient API.
            </p>
          </div>

          <div className="relative w-full sm:max-w-sm">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#82939d]">
              ⌕
            </span>
            <input
              value={query}
              onChange={(event) => handleSearch(event.target.value)}
              placeholder="Search patients..."
              aria-label="Search patients"
              className="w-full rounded-xl border border-[#dfe7ec] bg-[#f9fbfc] py-3 pl-9 pr-10 text-sm text-[#193342] outline-none transition focus:border-[#087f8c] focus:ring-4 focus:ring-[#087f8c]/10"
            />
            {query && (
              <button
                onClick={() => handleSearch("")}
                aria-label="Clear search"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#82939d] hover:text-[#193342]"
              >
                ×
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="m-5 rounded-xl border border-[#f2d2d3] bg-[#fff5f5] p-4">
            <p className="text-sm font-semibold text-[#b8474c]">{error}</p>
            <button
              onClick={() => void loadPatients()}
              className="mt-3 rounded-lg border border-[#e7babc] px-3 py-2 text-xs font-semibold text-[#a83e44] hover:bg-white"
            >
              Try again
            </button>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left">
            <thead>
              <tr className="bg-[#f7f9fa] text-[10px] font-bold uppercase tracking-wider text-[#82939d]">
                <th className="px-5 py-4">Patient</th>
                <th className="px-4 py-4">MRN</th>
                <th className="px-4 py-4">Age</th>
                <th className="px-4 py-4">Gender</th>
                <th className="px-4 py-4">Admission</th>
                <th className="px-5 py-4">Status</th>
                  <th className="px-5 py-4">Clinical guidance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#edf1f3]">
              {isLoading &&
                Array.from({ length: 5 }).map((_, index) => (
                  <tr key={`loading-${index}`}>
                    {Array.from({ length: 6 }).map((__, cell) => (
                      <td key={cell} className="px-5 py-5">
                        <div className="h-4 animate-pulse rounded bg-[#edf2f4]" />
                      </td>
                    ))}
                  </tr>
                ))}

              {!isLoading && !error && data?.items?.map((patient) => (
                <tr key={patient.id} className="transition hover:bg-[#f8fbfb]">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <PatientAvatar patient={patient} />
                      <div>
                        <p className="font-semibold text-[#253f4c]">
                          {patient.first_name} {patient.last_name}
                        </p>
                        <p className="mt-1 text-xs text-[#91a0a9]">
                          Patient record
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <span className="rounded-md bg-[#f1f5f7] px-2 py-1 font-mono text-xs text-[#526b78]">
                      {patient.mrn}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-sm text-[#526b78]">
                    {calculateAge(patient.date_of_birth)}
                  </td>
                  <td className="px-4 py-4 text-sm text-[#526b78]">
                    {GENDER_LABELS[patient.gender] ?? patient.gender}
                  </td>
                  <td className="px-4 py-4 text-sm text-[#526b78]">
                    {patient.is_admitted ? "Currently admitted" : "—"}
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[10px] font-bold ${
                        patient.is_admitted
                          ? "bg-[#e5f6ef] text-[#21805f]"
                          : "bg-[#f0f3f5] text-[#738391]"
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          patient.is_admitted ? "bg-[#319a77]" : "bg-[#9aa8b0]"
                        }`}
                      />
                      {patient.is_admitted ? "Admitted" : "Not admitted"}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <button type="button" onClick={() => setGuidancePatient(patient)}
                      className="whitespace-nowrap rounded-lg border border-[#b9e3df] bg-[#effaf8] px-3 py-2 text-xs font-semibold text-[#087f8c] hover:bg-[#dff5f1]">
                      Tests &amp; Care Guidance
                    </button>
                  </td>
                </tr>
              ))}

              {!isLoading && !error && (!data?.items || data.items.length === 0) && (
                <tr>
                  <td colSpan={7} className="px-5 py-16 text-center">
                    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#edf6f6] text-2xl text-[#087f8c]">
                      ⌕
                    </div>
                    <p className="font-semibold text-[#294452]">
                      No matching patients
                    </p>
                    <p className="mt-1 text-sm text-[#8797a1]">
                      Try a different search term.
                    </p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-3 border-t border-[#e8eef2] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-[#8797a1]">
            {data
              ? `Showing ${data.items.length ? (page - 1) * PAGE_SIZE + 1 : 0}–${Math.min(page * PAGE_SIZE, data.total)} of ${data.total} records`
              : "Waiting for patient records"}
          </p>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              className="rounded-lg border border-[#dfe7ec] px-3 py-2 text-xs font-semibold text-[#526b78] hover:bg-[#f6f9fa] disabled:cursor-not-allowed disabled:opacity-40"
            >
              ← Previous
            </button>
            <span className="min-w-16 text-center text-xs font-semibold text-[#526b78]">
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages || isLoading}
              onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              className="rounded-lg border border-[#dfe7ec] px-3 py-2 text-xs font-semibold text-[#526b78] hover:bg-[#f6f9fa] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>
      </section>

      {showAddModal && (
        <AddPatientModal
          onClose={() => setShowAddModal(false)}
          onCreated={handlePatientCreated}
        />
      )}
      {guidancePatient && (
        <ClinicalGuidanceModal
          patientId={guidancePatient.id}
          patientName={`${guidancePatient.first_name} ${guidancePatient.last_name}`}
          onClose={() => setGuidancePatient(null)}
        />
      )}
    </AppLayout>
  );
}
