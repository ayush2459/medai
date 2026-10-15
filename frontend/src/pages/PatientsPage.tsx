import { useEffect, useState } from "react";
import { AppLayout } from "../components/AppLayout";
import { AddPatientModal } from "../components/AddPatientModal";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { PaginatedPatients } from "../lib/types";

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
  const monthDiff = today.getMonth() - birth.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
    age -= 1;
  }
  return age;
}

export function PatientsPage() {
  const { user } = useAuth();
  const canAddPatients = user?.role === "admin" || user?.role === "doctor" || user?.role === "nurse";

  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedPatients | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  function loadPatients() {
    setIsLoading(true);
    setError(null);
    api
      .get<PaginatedPatients>("/api/patients", {
        params: { search: query || undefined, page, page_size: PAGE_SIZE },
      })
      .then((res) => setData(res.data))
      .catch(() => setError("Could not load patients."))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    const handle = setTimeout(loadPatients, query ? 300 : 0);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, page]);

  function handlePatientCreated() {
    setShowAddModal(false);
    setPage(1);
    setQuery("");
    loadPatients();
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <AppLayout title="Patients">
      <div className="mb-4 flex items-center justify-between gap-4">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
          placeholder="Search by name or MRN…"
          className="w-full max-w-sm rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-primary"
        />
        {canAddPatients && (
          <button
            onClick={() => setShowAddModal(true)}
            className="shrink-0 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark"
          >
            + Add Patient
          </button>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        {error && <div className="p-4 text-sm text-danger">{error}</div>}

        {!error && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-bg text-xs font-medium uppercase tracking-wide text-ink-muted">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">MRN</th>
                <th className="px-4 py-3">Age</th>
                <th className="px-4 py-3">Gender</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-ink-muted">
                    Loading…
                  </td>
                </tr>
              )}
              {!isLoading && data?.items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-ink-muted">
                    No patients found.
                  </td>
                </tr>
              )}
              {!isLoading &&
                data?.items.map((p) => (
                  <tr key={p.id} className="hover:bg-bg">
                    <td className="px-4 py-3 font-medium text-ink">
                      {p.first_name} {p.last_name}
                    </td>
                    <td className="tabular-figures px-4 py-3 text-ink-muted">{p.mrn}</td>
                    <td className="tabular-figures px-4 py-3 text-ink-muted">{calculateAge(p.date_of_birth)}</td>
                    <td className="px-4 py-3 text-ink-muted">{GENDER_LABELS[p.gender] ?? p.gender}</td>
                    <td className="px-4 py-3">
                      {p.is_admitted ? (
                        <span className="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-medium text-primary-dark">
                          Admitted{p.ward ? ` · ${p.ward}` : ""}
                        </span>
                      ) : (
                        <span className="rounded-full bg-bg px-2 py-0.5 text-xs font-medium text-ink-muted">
                          Outpatient
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>

      {data && data.total > 0 && (
        <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
          <span>
            Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {showAddModal && (
        <AddPatientModal onClose={() => setShowAddModal(false)} onCreated={handlePatientCreated} />
      )}
    </AppLayout>
  );
}
