# Assumptions

This file records every assumption made during implementation that was not explicitly specified
in the challenge brief. These will be updated as decisions are made.

---

## Architecture

**A1.** The GlucoTwin API endpoints are mounted at `/api/v1/` prefix inside the existing FastAPI
backend (`backend/app/main.py`) — not as a separate microservice. The existing `/api/*` routes
are preserved untouched. This avoids CORS complexity and keeps the demo single-process.

**A2.** Twin state is stored in an SQLite file (`twin_state.db`) at the backend working directory.
This keeps it zero-setup for the demo (no extra migration step) while being separate from the
PostgreSQL database used by the existing application.

**A3.** The GlucoTwin synthetic patient IDs (`SYN-0001` ... `SYN-0400`) are different from the
existing PostgreSQL Patient UUIDs. The GlucoTwin endpoints only operate on synthetic T2D patients
from the generated dataset, not on the existing seeded hospital patients.

---

## Data Generation

**D1.** "400 synthetic adult T2D patients" with fixed seed 42. All 400 patients are generated and
saved to Parquet. The `data/sample/` directory contains the first 50 patients with only 3 days of
wearable data for fast demo loading.

**D2.** The wearable simulator runs 21 days for each patient. Full data (~400 patients × 21 days ×
288 CGM readings) is gitignored. Only the sample is committed.

**D3.** The genetic risk score is a synthetic float in [0, 1] derived from a weighted combination
of age, BMI, family history (boolean), and random noise. It is not based on real genomic data.

**D4.** "Family history" is a boolean (True/False). Positive family history probability = 0.35.

**D5.** Comorbidities represented: hypertension (boolean) and CKD stage (0–3 integer). Their
prevalence is correlated with age and BMI.

**D6.** Medication groups: metformin (most common), sulfonylurea, insulin (including combo),
"other" (DPP-4 or no medication). The hypoglycaemia_risk_flag is True for sulfonylurea and
insulin users.

**D7.** Simulator duration is exactly 21 days (30 240 minutes) at 5-minute intervals = 6048 CGM
readings per patient. Heart rate, HRV, and sleep stage are stored at 5-minute resolution; steps
are 5-minute cumulative counts.

**D8.** Missing CGM readings are represented as NaN (not 0, not -1). Sensor dropout probability
is ~2% per reading, with bursts (consecutive dropout probability = 60%).

---

## Model

**M1.** LightGBM is used for both the hyperglycaemia and hypoglycaemia models. The optional GRU
(PyTorch) is implemented but disabled by default (flag `--gru`). Results in `metrics.json`
always report the LightGBM calibrated model.

**M2.** Calibration is isotonic regression on the validation set. Platt scaling is not used
because isotonic regression generalises better on the synthetic data sizes expected here.

**M3.** The "mean lead time" metric is computed at a fixed operating threshold of 0.3 (30%
predicted probability triggers an alert), applied to the test set.

**M4.** Stratification bands:
  - Medication group: `{insulin, sulfonylurea}` vs `{metformin, other}`
  - Age band: `<50`, `50-65`, `>65`
  - HbA1c band: `<7.5%`, `7.5-9%`, `>9%`

**M5.** SHAP explanations are computed using `shap.TreeExplainer` on the trained LightGBM model,
with `check_additivity=False` to handle NaN inputs.

---

## Rules Engine

**R1.** All rule intervals are placeholder defaults based on commonly cited diabetes monitoring
practice. Every rule carries `review_status = "pending clinician review"`. The system labels
them as candidates, never orders.

**R2.** For R5 (CGM-triggered review), default thresholds are: time-in-range < 70%, or ≥ 2 hypo
events in the last 14 days. These are clearly marked as placeholder thresholds that a clinician
should configure.

**R3.** "Missing information" means the required date or value field is None in the twin state.
The rule engine returns `{"status": "missing_data", "message": "Last HbA1c date not recorded"}`
rather than a suggestion.

---

## API / Frontend

**F1.** The `POST /demo/advance/{patient_id}` endpoint replays up to 60 minutes (12 readings)
of pre-generated wearable data per call. The `n_minutes` query parameter (default 60, max 480)
controls how much simulated time is advanced.

**F2.** The SYNTHETIC DATA banner is a fixed top bar in the GlucoTwin page only (not in
existing pages, to avoid touching their layouts).

**F3.** Audit log entries are stored in the SQLite `twin_state.db` in an `audit_log` table.

**F4.** The `/api/v1/predictions` endpoint requires authentication (same Bearer JWT as existing
endpoints). The `/api/v1/health` endpoint is public.

---

## Evaluation

**E1.** Results in `results/metrics.json` are produced by running `python twin/evaluate.py`
after training. The README table is populated from this file. Numbers are never hardcoded.

**E2.** If the model achieves suspiciously perfect metrics (AUROC > 0.99), the evaluate script
prints a leakage warning and records it in `metrics.json` under `"leakage_warning"`.
