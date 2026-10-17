# Repository Audit — MedIntel AI → GlucoTwin

**Date:** 2026-10-17  
**Auditor:** Kiro AI Agent

---

## 1. What Exists

### Frontend (React + TypeScript + Vite + Tailwind CSS v4 + Recharts)

| File / Component | What it does |
|---|---|
| `src/App.tsx` | React Router routes: `/` (redirect), `/login`, `/dashboard`, `/icu-risk`, `/patients` |
| `src/lib/auth.tsx` | AuthContext: login/logout, JWT token storage in localStorage, user hydration via `/api/auth/me` |
| `src/lib/api.ts` | Axios instance with Bearer token interceptor; clears tokens on 401 |
| `src/lib/types.ts` | TS types: CurrentUser, TokenPair, ExecutiveSummary, PatientSummary, IcuRiskResponse, etc. |
| `src/pages/LoginPage.tsx` | Email + password login form |
| `src/pages/ExecutiveDashboard.tsx` | KPI cards + Recharts LineChart + BarChart from `/api/analytics/executive` |
| `src/pages/PatientsPage.tsx` | Paginated patient table with debounced search; role-gated "+ Add Patient" |
| `src/pages/IcuRiskPage.tsx` | Patient search → `/api/ml/icu-risk/{id}` → probability, risk badge, top factors |
| `src/components/AppLayout.tsx` | 224px sidebar (Executive Overview, ICU Risk Check, Patients, Disease Analytics placeholder) + header |
| `src/components/KpiCard.tsx` | Reusable KPI card with accent colour variants |
| `src/components/AddPatientModal.tsx` | Modal form to POST to `/api/patients` |
| `src/components/ProtectedRoute.tsx` | Auth guard; spinner or redirect to /login |
| `src/index.css` | Tailwind v4 theme tokens (--color-primary #0B6E63, --color-danger #B5433A, etc.) |

**State management:** No external library. AuthContext + useState/useEffect per page.  
**Routing:** React Router v7.  
**Styling:** Tailwind CSS v4 with design tokens. Custom font: Public Sans + IBM Plex Mono.

### Backend (FastAPI + SQLAlchemy 2.0 + PostgreSQL + JWT Auth)

| Module | What it does |
|---|---|
| `app/main.py` | FastAPI app; CORS + SessionMiddleware; registers 5 routers |
| `app/routers/auth.py` | `/api/auth` — register, login (OAuth2 form), refresh, /me |
| `app/routers/oauth.py` | `/api/auth/oauth` — Google OAuth scaffold (requires credentials) |
| `app/routers/patients.py` | `/api/patients` — full CRUD + diagnoses, prescriptions, labs, notes |
| `app/routers/analytics.py` | `/api/analytics/executive` — KPI summary |
| `app/routers/ml.py` | `/api/ml/icu-risk/{patient_id}` — XGBoost ICU risk inference |
| `app/models/user.py` | User (roles: admin/doctor/nurse/researcher, JWT auth, OAuth scaffold) |
| `app/models/patient.py` | Patient + Diagnosis + Prescription + LabResult + DoctorNote |
| `app/models/clinical_events.py` | VitalSign + AdmissionEvent + Observation |
| `app/ml/features.py` | Feature engineering from DB → ICU risk feature row |
| `app/ml/inference.py` | XGBoost load + predict; ModelNotTrainedError |
| `app/ml/train_icu_risk.py` | Train XGBoost from AdmissionEvent data, save joblib bundle |
| `app/seed.py` | Seed 150 synthetic patients with vitals/admissions for demo |
| `app/core/config.py` | pydantic-settings Settings singleton |
| `app/core/security.py` | bcrypt hash/verify + JWT create/decode |
| `app/core/deps.py` | get_current_user + require_roles dependencies |
| `app/db/session.py` | SQLAlchemy engine + SessionLocal + Base + get_db |
| `alembic/versions/` | 3 migrations: initial schema, clinical events, observations |

### Infrastructure
- **docker-compose.yml:** postgres:16 + redis:7-alpine (backend not containerised)
- **requirements.txt:** FastAPI 0.115, SQLAlchemy 2.0, XGBoost, scikit-learn, pandas, pydantic v2

---

## 2. What is Missing vs. GlucoTwin Spec

| Required | Status |
|---|---|
| `data/generate_ehr.py` (400 T2D patients) | ❌ Missing |
| `data/simulate_wearable.py` (21-day CGM simulator) | ❌ Missing |
| `data/build_dataset.py` (combined feature dataset) | ❌ Missing |
| `data/sample/` (committed small sample) | ❌ Missing |
| `twin/features.py` (glucose/HRV/EHR features) | ❌ Missing (existing features.py is for ICU, different domain) |
| `twin/state.py` (per-patient persistent twin state) | ❌ Missing |
| `twin/model_train.py` (LightGBM hypo/hyper) | ❌ Missing |
| `twin/predict.py` (prediction + calibration) | ❌ Missing |
| `twin/explain.py` (SHAP top-5 factors) | ❌ Missing |
| `twin/evaluate.py` (AUROC, AUPRC, ablation) | ❌ Missing |
| `rules/rules_v1.yaml` | ❌ Missing |
| `rules/evidence_register.csv` | ❌ Missing |
| `rules/engine.py` | ❌ Missing |
| `results/metrics.json` + figures | ❌ Missing |
| New API endpoints (twin, predict, investigations, decisions, demo/advance) | ❌ Missing |
| New frontend page: GlucoTwin Dashboard (CGM chart, risk alerts, twin state, investigation suggestions) | ❌ Missing |
| Sidebar nav link for GlucoTwin | ❌ Missing |
| pytest tests for all new modules | ❌ Missing |
| Makefile | ❌ Missing |
| LICENSE | ❌ Missing |
| `docs/ASSUMPTIONS.md`, `docs/ARCHITECTURE.md` | ❌ Missing |

---

## 3. Integration Plan

### Principle: Extend, Never Break

1. **Backend:** Add a new router `backend/app/routers/glucotwin.py` mounted at `/api/v1` prefix alongside the existing `/api/*` routes. Twin state uses SQLite (separate from the Postgres DB). The existing PostgreSQL schema is not touched.

2. **Frontend:** Add a new route `/glucotwin` with a new page `GlucoTwinPage.tsx`. Add a nav link in `AppLayout.tsx` under the existing links. Reuse `KpiCard`, `AppLayout`, styling tokens, `api.ts` client, and `useAuth()`. Do NOT replace or alter existing pages.

3. **Data:** `data/` directory lives at the repo root (not inside backend). Parquet files and large CSVs are gitignored. Only `data/sample/*.parquet` (≤50 patients, 3 days) is committed.

4. **ML:** `twin/` directory at repo root. Trains against data files, saves models to `twin/models/` (gitignored except the committed calibrated model bundle for demo).

5. **Rules:** `rules/` at repo root. YAML + CSV committed. Engine is pure Python with no DB dependency for fast unit tests.

6. **Tests:** `tests/` at repo root. pytest with coverage for simulator, features, model split, rules, and API contract tests.

7. **Docker:** Update `docker-compose.yml` to also containerise the backend (with GlucoTwin endpoints). Keep postgres and redis services unchanged.

8. **README:** Replace with GlucoTwin-first README while keeping the existing MedIntel AI section as a sub-section.
