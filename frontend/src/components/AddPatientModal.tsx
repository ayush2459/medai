import { useState, type FormEvent } from "react";
import { api } from "../lib/api";
import type { PatientCreate } from "../lib/types";

interface AddPatientModalProps {
  onClose: () => void;
  onCreated: () => void;
}

const EMPTY_FORM: PatientCreate = {
  mrn: "",
  first_name: "",
  last_name: "",
  date_of_birth: "",
  gender: "male",
  phone: "",
  email: "",
  blood_type: "",
};

export function AddPatientModal({ onClose, onCreated }: AddPatientModalProps) {
  const [form, setForm] = useState<PatientCreate>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function update<K extends keyof PatientCreate>(key: K, value: PatientCreate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      // Strip empty-string optionals so we don't send "" for fields the backend treats as absent
      const payload: PatientCreate = { ...form };
      (Object.keys(payload) as (keyof PatientCreate)[]).forEach((key) => {
        if (payload[key] === "") delete payload[key];
      });

      const response = await api.post("/api/patients", payload);
      
      // Check if response has the expected patient ID - in demo mode it will
      if (response.data?.id) {
        // Successfully created (either in DB or demo mode in-memory)
        onCreated();
      } else {
        setError("Patient accepted but response unexpected. Refreshing...");
        setTimeout(onCreated, 500);
      }
    } catch (err: any) {
      if (err.response?.status === 409) {
        setError("A patient with this MRN already exists.");
      } else if (err.response?.status === 422) {
        const detail = err.response.data?.detail;
        const message = Array.isArray(detail) ? detail[0]?.msg : detail;
        setError(message || "Please check the form fields.");
      } else if (err.response?.status === 403) {
        setError("Your role isn't permitted to create patients.");
      } else {
        setError("Could not create patient. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-border bg-surface p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">Add Patient</h2>
          <button onClick={onClose} className="text-ink-muted hover:text-ink" aria-label="Close">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">MRN *</label>
              <input
                required
                maxLength={32}
                value={form.mrn}
                onChange={(e) => update("mrn", e.target.value)}
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
                placeholder="MRN-1234"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">Date of birth *</label>
              <input
                required
                type="date"
                value={form.date_of_birth}
                onChange={(e) => update("date_of_birth", e.target.value)}
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">First name *</label>
              <input
                required
                maxLength={100}
                value={form.first_name}
                onChange={(e) => update("first_name", e.target.value)}
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">Last name *</label>
              <input
                required
                maxLength={100}
                value={form.last_name}
                onChange={(e) => update("last_name", e.target.value)}
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">Gender *</label>
              <select
                required
                value={form.gender}
                onChange={(e) => update("gender", e.target.value as PatientCreate["gender"])}
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">Blood type</label>
              <input
                maxLength={5}
                value={form.blood_type}
                onChange={(e) => update("blood_type", e.target.value)}
                placeholder="O+"
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">Phone</label>
              <input
                maxLength={30}
                value={form.phone}
                onChange={(e) => update("phone", e.target.value)}
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">Email</label>
              <input
                type="email"
                maxLength={255}
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-primary"
              />
            </div>
          </div>

          {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-ink-muted hover:bg-bg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-60"
            >
              {isSubmitting ? "Saving…" : "Add Patient"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
