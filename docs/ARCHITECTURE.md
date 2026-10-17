# GlucoTwin — System Architecture

## Mermaid Diagram

```mermaid
flowchart TD
    subgraph DataSources["Data Sources"]
        EHR["Stream 1: Synthetic EHR\n(400 T2D patients)\nAge, BMI, HbA1c, eGFR,\nmedications, comorbidities,\ngenetic risk score"]
        WAR["Stream 2: Simulated Wearables\n(21-day time series)\nCGM 5-min, HRV, sleep,\nsteps, heart rate"]
    end

    subgraph DataPipeline["Data Pipeline (data/)"]
        GEN["generate_ehr.py\nSynthea-style CSV schema"]
        SIM["simulate_wearable.py\nPhysiologically inspired\nglucose + wearable sim"]
        BLD["build_dataset.py\nEarly fusion feature\nengineering per forecast time"]
    end

    subgraph TwinCore["Digital Twin Core (twin/)"]
        FEAT["features.py\nCanonical feature columns\nNaN imputation medians"]
        STATE["state.py\nSQLite per-patient state\nTIR, hypo events, sleep,\nsteps, HRV trend, test dates"]
        TRAIN["model_train.py\nLightGBM (hyper + hypo)\nPatient-wise split 70/15/15\nIsotonic calibration"]
        PRED["predict.py\nCalibratedClassifierCV\np_hyper_120, p_hypo_120\nRisk bands: low/med/high"]
        EXPL["explain.py\nSHAP TreeExplainer\nTop-5 factors per prediction"]
        EVAL["evaluate.py\nAUROC, AUPRC, Brier\nCalibration, lead time\nAblation table"]
    end

    subgraph RulesEngine["Rule Engine (rules/)"]
        YAML["rules_v1.yaml\nVersioned investigation rules\nR1-R6 (pending clinician review)"]
        REG["evidence_register.csv\nSource URLs + review status"]
        ENG["engine.py\nEvaluates rules vs twin state\nProduces review prompts only\nNever orders"]
    end

    subgraph API["FastAPI Backend (backend/)"]
        GT["glucotwin.py router\n/api/v1/..."]
        EXIST["Existing MedIntel AI routes\n/api/auth /api/patients\n/api/analytics /api/ml"]
    end

    subgraph Frontend["React + TypeScript Frontend (frontend/)"]
        DASH["GlucoTwinPage.tsx\nPatient selector\nCGM live chart + thresholds\nRisk alert cards + SHAP why\nTwin state summary\nInvestigation table\nClinician decision buttons\nAudit log"]
        EXIST_UI["Existing MedIntel AI pages\nExecutive Dashboard\nICU Risk Check\nPatients"]
    end

    subgraph Storage["Storage"]
        PG["PostgreSQL\nUsers, hospital patients,\nclinical events (existing)"]
        SQ["SQLite (twin_state.db)\nPer-patient twin state\nPredictions + audit log"]
        PARQ["Parquet files (data/)\nEHR cohort + wearable TS\n(gitignored, sample committed)"]
        MODELS["Serialised models (twin/models/)\n.pkl bundles + medians.json"]
    end

    EHR --> GEN
    WAR --> SIM
    GEN --> BLD
    SIM --> BLD
    BLD --> TRAIN
    TRAIN --> MODELS
    MODELS --> PRED
    MODELS --> EXPL
    BLD --> EVAL

    FEAT --> TRAIN
    FEAT --> PRED

    PRED --> STATE
    STATE --> ENG
    YAML --> ENG
    REG --> ENG

    ENG --> GT
    PRED --> GT
    EXPL --> GT
    STATE --> GT
    EXIST --> GT

    GT --> SQ
    GT --> PG
    GT --> PARQ

    EXIST --> PG
    PG --> EXIST_UI

    GT --> DASH
    EXIST --> EXIST_UI
```

## Layer Descriptions

| Layer | Files | Responsibility |
|---|---|---|
| Data Sources | `data/generate_ehr.py`, `data/simulate_wearable.py` | Generate 400 synthetic T2D patients + 21 days wearable data |
| Feature Engineering | `data/build_dataset.py`, `twin/features.py` | Early fusion of CGM features + EHR context per forecast time |
| Twin Core | `twin/state.py`, `twin/model_train.py`, `twin/predict.py`, `twin/explain.py` | Per-patient persistent state, LightGBM prediction, SHAP explanations |
| Evaluation | `twin/evaluate.py` | AUROC/AUPRC/Brier/calibration/lead-time + ablation table |
| Rule Engine | `rules/engine.py`, `rules/rules_v1.yaml` | Versioned investigation suggestions (never orders) |
| API | `backend/app/routers/glucotwin.py` | 12 REST endpoints at `/api/v1/` |
| Frontend | `frontend/src/pages/GlucoTwinPage.tsx` | Clinician dashboard: CGM chart, risk cards, investigations, audit log |
| Storage | PostgreSQL + SQLite + Parquet | Separated: relational (existing), twin state (SQLite), datasets (Parquet) |

## Data Flow

1. EHR generator creates 400 synthetic T2D patients (Parquet)
2. Wearable simulator generates 21 days × 288 CGM readings per patient (Parquet)
3. Dataset builder merges both streams into forecast-ready feature rows (Parquet)
4. LightGBM trains on 70% of patients (patient-wise split), validates on 15%, tests on 15%
5. Calibrated models saved to `twin/models/*.pkl`
6. API loads patient data from Parquet cache; builds features on demand
7. Rule engine reads twin state from SQLite and evaluates against `rules_v1.yaml`
8. Frontend polls `/api/v1/twin/{patient_id}` and displays everything in one screen

## Safety Design

- All data is synthetic (no real patient data)
- Every alert shows SHAP top-5 factors
- Every investigation suggestion is labelled "pending clinician review"
- Every suggestion carries rule ID, version, and source URL
- Missing data returns "missing_data" status, never a guess
- R6 (context override) is always active: recent lab results do not suppress
  suggestions when a high-risk alert or therapy change is active
- Clinician decisions (accept/defer/override) are stored in an audit log
- A persistent "SYNTHETIC DATA — NOT FOR CLINICAL USE" banner is shown at all times
