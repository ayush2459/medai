# GlucoTwin — Digital Twin for Type 2 Diabetes

**A dual-stream digital twin prototype for forecasting glycaemic events and supporting clinician review.**

> **SYNTHETIC DATA ONLY — NOT FOR CLINICAL USE.** This is a research and education proof of concept, not a medical device. It has not been clinically validated and must not be used to diagnose, prescribe, or make treatment decisions. Clinical decisions remain with a qualified clinician.

## Team and institution

| Field | Details |
|---|---|
| Project title | **GlucoTwin — Digital Twin for Type 2 Diabetes** |
| Parent platform | MedIntel AI / MedAI |
| Challenge | Digital Twin Challenge 2026 — Happiest Health |
| Team name | **[ADD OFFICIAL TEAM NAME]** |
| College / incubator | **[ADD COLLEGE OR INCUBATOR NAME]** |
| Team leader | **Ayush Gupta** — [add submission email and phone] |
| Team members | [Add all members' full names and roles] |

**Before submission:** replace every bracketed placeholder with verified details. Do not publish personal contact details unless the team leader intends them to be public.

## Problem statement

Glucose excursions can occur between scheduled diabetes appointments, while clinical history, laboratory values, medication context, and sensor trends may be reviewed separately. This project explores whether a patient-specific digital-twin workflow can combine longitudinal clinical context with recent sensor trends to surface potential glycaemic events and provide a consolidated review experience.

## Healthcare use case

**Primary user:** treating doctor or diabetes care team.

The prototype combines synthetic EHR context (demographics, diagnoses, labs such as HbA1c/eGFR, medications and comorbidities) with simulated wearable time series (CGM, HRV, sleep and steps). It estimates the probability of hyperglycaemia (glucose >180 mg/dL) and hypoglycaemia (glucose <70 mg/dL) over a nominal two-hour forecast horizon, then presents review prompts and an audit workflow.

The system does not automatically order tests, change medication, or prescribe treatment. Investigation rules and thresholds remain pending clinician review.

## Architecture

1. Generate synthetic EHR and simulated wearable time-series data.
2. Validate inputs and engineer time-window features.
3. Fuse sensor-derived features with EHR context.
4. Run the LightGBM prediction pipeline.
5. Maintain twin state and present feature-contribution explanations where configured.
6. Generate versioned investigation review prompts.
7. Serve results through FastAPI to a React/TypeScript clinician dashboard and audit workflow.

- Architecture diagram: [`docs/architecture.pdf`](docs/architecture.pdf)
- Architecture source: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Presentation PDF: [`docs/presentation.pdf`](docs/presentation.pdf)
- Editable PowerPoint: [`docs/presentation.pptx`](docs/presentation.pptx)

## Technical stack

| Area | Technology | Role |
|---|---|---|
| Language | Python 3.11+ | Data generation, model pipeline, API and evaluation |
| EHR simulation | Custom Synthea-style Python generator | Reproducible synthetic clinical context |
| Wearable simulation | NumPy, SciPy, Pandas | Simulated CGM, HRV, sleep and steps |
| ML | LightGBM, scikit-learn | Tabular classification and evaluation |
| Explainability | SHAP / feature-contribution layer where configured | Interpretation support |
| API | FastAPI, Pydantic, Uvicorn | Typed service layer |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Recharts | Clinician-facing dashboard |
| Storage | PostgreSQL, SQLite twin state, Parquet datasets | Application state and experimental data |
| Clinical guidance | Versioned rules; optional Ollama/hosted LLM draft guidance | Clinician-facing review support only |
| Tests/tooling | pytest, Docker Compose, Makefile | Testing and reproducible workflows |
| Interoperability | HL7 FHIR R4 mapping (design direction) | Future integration pathway |

Exact versions and optional components depend on the checked-out project configuration. Confirm dependency files before deployment.

## Model and evaluation

The current evaluation scripts generated these headline metrics from `data/dataset.parquet`:

| Target | AUROC | AUPRC | Brier score | Positive rate | Samples | Mean lead time |
|---|---:|---:|---:|---:|---:|---:|
| Hyperglycaemia | 0.9192 | 0.8277 | 0.0652 | 25.73% | 54,946 | 14,279 min* |
| Hypoglycaemia | 0.5000 | 0.0192 | 0.0192 | 1.92% | 114,440 | Not available |

Baseline AUROC from `results/metrics.json`:

| Target | Persistence | Linear extrapolation |
|---|---:|---:|
| Hyperglycaemia | 0.5000 | 0.5560 |
| Hypoglycaemia | 0.5000 | 0.4984 |

### Ablation results

| Target | Feature set | AUROC | AUPRC |
|---|---|---:|---:|
| Hyperglycaemia | EHR only | 0.8538 | 0.6414 |
| Hyperglycaemia | CGM only | 0.9520 | 0.8802 |
| Hyperglycaemia | CGM + wearable | 0.9786 | 0.9408 |
| Hyperglycaemia | Full fusion | 0.9789 | 0.9414 |
| Hypoglycaemia | EHR only | 0.7260 | 0.0342 |
| Hypoglycaemia | CGM only | 0.6366 | 0.0371 |
| Hypoglycaemia | CGM + wearable | 0.7154 | 0.0446 |
| Hypoglycaemia | Full fusion | 0.8264 | 0.0616 |

**Evaluation caveat:** headline metrics in `results/metrics.json` do not match corresponding full-fusion values in `results/ablation.csv` (hypoglycaemia AUROC: 0.5000 vs 0.8264). The evaluation paths or data processing must be reconciled before performance claims are made. The reported hyperglycaemia mean lead time is about 9.9 days and requires verification against the event/alert definition. These are experimental synthetic-data results, not independently validated clinical performance.

## Data sources and limitations

- The demo is designed around synthetic EHR and simulated wearable data.
- Do not commit real patient records or credentials.
- Synthetic data can test software and pipeline behaviour but cannot establish clinical safety, real-world generalisation, or clinical utility.
- Any optional third-party dataset must be used under its own licence and terms; do not redistribute it unless explicitly permitted.

## Open-source licence

The code is intended to be released under the **MIT License**; see [`LICENSE`](LICENSE). MIT applies to code in this repository and does not grant rights to third-party datasets, logos, standards, or assets. Review third-party notices before distribution.

## Documents

- Architecture: [`docs/architecture.pdf`](docs/architecture.pdf)
- Presentation: [`docs/presentation.pdf`](docs/presentation.pdf)
- Editable presentation: [`docs/presentation.pptx`](docs/presentation.pptx)
- Demo video link: [`docs/video_link.md`](docs/video_link.md)

## Running and evaluation

Follow the repository's dependency files and environment examples. Run commands from the repository root. The evaluation script generates `results/metrics.json` and `results/ablation.csv`. Until the Makefile import path is corrected, the working evaluation command may require `PYTHONPATH=. python twin/evaluate.py`.

## Safety and future work

Before real-world evaluation, this project requires clinician review of rules and thresholds, validation on appropriate consented and de-identified data, patient-wise leakage checks, prospective evaluation, privacy/security review, and applicable regulatory assessment. Future work includes wearable/EHR interoperability, reconciled evaluation, clinician feedback studies, and validation across diverse patient groups.

---
**GlucoTwin / MedIntel AI** · Research prototype · Synthetic data only · Not for clinical use
