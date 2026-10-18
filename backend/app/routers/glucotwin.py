"""
backend/app/routers/glucotwin.py
================================
GlucoTwin API endpoints mounted at /api/v1 prefix.

Endpoints
---------
POST  /api/v1/ehr/patients            – load / upsert a synthetic EHR patient
POST  /api/v1/stream/readings         – ingest CGM + wearable readings
GET   /api/v1/patients                – list synthetic T2D patients
GET   /api/v1/patients/{id}/cgm       – recent CGM readings for a patient
GET   /api/v1/twin/{patient_id}       – current twin state + latest forecast
GET   /api/v1/predict/{patient_id}    – fresh prediction + top factors
GET   /api/v1/investigations/{patient_id} – rule-based investigation suggestions
POST  /api/v1/decisions               – record clinician decision
GET   /api/v1/audit                   – audit log
GET   /api/v1/health                  – service health
POST  /api/v1/demo/advance/{patient_id} – replay next N minutes of simulated data

Note: The twin state and EHR cohort are loaded from Parquet files (generated
by data/ scripts).  They are served from a SQLite cache for fast reads.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import get_current_user
from app.models.user import User

# ── Path setup ────────────────────────────────────────────────────────────────
# The twin/ and rules/ directories sit at the repo root, one level above backend/
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ── Import domain modules (lazy to avoid import errors if not yet installed) ─
def _import_twin():
    try:
        from twin.state import (
            get_twin_state, save_audit_entry, save_prediction, get_audit_log, init_db,
        )
        from twin.predict import predict_row, ModelNotTrainedError
        from twin.explain import explain_row
        from rules.engine import evaluate_rules
        return get_twin_state, save_audit_entry, save_prediction, get_audit_log, init_db, predict_row, ModelNotTrainedError, explain_row, evaluate_rules
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Twin modules not available: {e}"
        )

# ── Data paths ────────────────────────────────────────────────────────────────
DATA_DIR    = REPO_ROOT / "data"
SAMPLE_DIR  = DATA_DIR / "sample"
TWIN_DB     = REPO_ROOT / "twin_state.db"

# ── Pydantic schemas ──────────────────────────────────────────────────────────

class EHRPatientIn(BaseModel):
    patient_id: str
    age: float
    sex: str
    bmi: float
    diabetes_duration_years: float
    hypertension: bool = False
    ckd_stage: int = 0
    family_history: bool = False
    genetic_risk_score: float = Field(0.2, ge=0.0, le=1.0)
    hba1c_latest: Optional[float] = None
    insulin_flag: bool = False
    sulfonylurea_flag: bool = False


class WearableReading(BaseModel):
    patient_id: str
    timestamp: datetime
    glucose_mg_dl: Optional[float] = None    # None = sensor dropout
    heart_rate: Optional[float] = None
    hrv_rmssd: Optional[float] = None
    steps: Optional[float] = None
    sleep_stage: Optional[int] = None        # 0=awake,1=light,2=deep,3=REM


class ReadingsIn(BaseModel):
    readings: list[WearableReading] = Field(..., min_length=1)


class DecisionIn(BaseModel):
    patient_id: str
    suggestion_type: str
    rule_id: Optional[str] = None
    rule_version: Optional[str] = None
    decision: str = Field(..., pattern="^(accept|defer|override)$")
    reason: Optional[str] = None


class TwinStateOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    patient_id: str
    updated_at: Optional[str]
    latest_reading_time: Optional[str]
    time_in_range_7d: Optional[float]
    hypo_events_14d: Optional[int]
    avg_sleep_h: Optional[float]
    steps_today: Optional[float]
    hrv_trend: Optional[int]
    last_hba1c_date: Optional[str]
    last_egfr_date: Optional[str]
    last_lipid_date: Optional[str]
    last_eye_date: Optional[str]
    last_foot_date: Optional[str]
    last_prediction_hyper: Optional[float]
    last_prediction_hypo: Optional[float]
    data_gap_flag: bool
    confidence_flag: str
    prediction: Optional[dict] = None
    investigations: list[dict] = []


class PredictionOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    patient_id: str
    p_hyper_120: Optional[float]
    p_hypo_120: Optional[float]
    risk_band_hyper: str
    risk_band_hypo: str
    top_factors_hyper: list[str]
    top_factors_hypo: list[str]
    model_version: str
    confidence_flag: str


# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/v1", tags=["glucotwin"])


# ── In-memory patient store (loaded from Parquet on first request) ────────────
_PATIENT_CACHE: dict[str, dict] = {}
_WEARABLE_CACHE: dict[str, pd.DataFrame] = {}
_DEMO_CURSOR: dict[str, int] = {}   # patient_id → last replayed reading index


def _load_patients() -> dict[str, dict]:
    if _PATIENT_CACHE:
        return _PATIENT_CACHE
    for d in (DATA_DIR, SAMPLE_DIR):
        p = d / "patients_with_flags.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            for _, row in df.iterrows():
                _PATIENT_CACHE[row["patient_id"]] = row.to_dict()
            return _PATIENT_CACHE
    return _PATIENT_CACHE


def _load_wearable(patient_id: str) -> Optional[pd.DataFrame]:
    if patient_id in _WEARABLE_CACHE:
        return _WEARABLE_CACHE[patient_id]
    for d in (DATA_DIR, SAMPLE_DIR):
        p = d / "wearable.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            sub = df[df["patient_id"] == patient_id].copy()
            if not sub.empty:
                _WEARABLE_CACHE[patient_id] = sub
                return sub
    return None


def _get_patient_or_404(patient_id: str) -> dict:
    patients = _load_patients()
    if patient_id not in patients:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found in GlucoTwin cohort")
    return patients[patient_id]


def _build_feature_dict(patient: dict, wearable_df: pd.DataFrame) -> Optional[dict]:
    """Build a single-row feature dict from the latest wearable data."""
    try:
        # Import build_patient_features inline to avoid circular deps
        sys.path.insert(0, str(REPO_ROOT / "data"))
        from build_dataset import _build_patient_features, LOOKBACK_STEPS  # noqa
        row = pd.Series(patient)
        feat_df = _build_patient_features(row, wearable_df)
        if feat_df is None or feat_df.empty:
            return None
        return feat_df.iloc[-1].to_dict()
    except Exception:
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health")
def glucotwin_health():
    """GlucoTwin service health check."""
    return {
        "status": "ok",
        "service": "glucotwin",
        "disclaimer": "SYNTHETIC DATA — NOT FOR CLINICAL USE",
    }


@router.post("/ehr/patients", status_code=201)
def upsert_ehr_patient(
    payload: EHRPatientIn,
    _current_user: User = Depends(get_current_user),
):
    """Load or update a synthetic T2D patient's EHR record."""
    _load_patients()
    _PATIENT_CACHE[payload.patient_id] = payload.model_dump()
    return {"patient_id": payload.patient_id, "status": "upserted"}


@router.post("/stream/readings", status_code=202)
def ingest_readings(
    payload: ReadingsIn,
    _current_user: User = Depends(get_current_user),
):
    """
    Ingest CGM and wearable readings for one or more patients.
    Validates schema, rejects duplicates (same patient + timestamp),
    and updates twin state.
    Missing glucose values (sensor dropout) must be sent as null.
    """
    (get_twin_state, save_audit_entry, save_prediction, get_audit_log, init_db,
     predict_row, ModelNotTrainedError, explain_row, evaluate_rules) = _import_twin()
    init_db(TWIN_DB)

    by_patient: dict[str, list[dict]] = {}
    for r in payload.readings:
        pid = r.patient_id
        by_patient.setdefault(pid, []).append({
            "patient_id":   pid,
            "timestamp":    r.timestamp,
            "glucose_mg_dl": r.glucose_mg_dl,
            "heart_rate":   r.heart_rate,
            "hrv_rmssd":    r.hrv_rmssd,
            "steps":        r.steps or 0.0,
            "sleep_stage":  r.sleep_stage or 0,
            "sensor_quality_flag": 0 if r.glucose_mg_dl is None else 1,
        })

    updated = []
    for pid, rows in by_patient.items():
        wdf = pd.DataFrame(rows)
        # Merge with existing cache
        existing = _WEARABLE_CACHE.get(pid, pd.DataFrame())
        merged = pd.concat([existing, wdf], ignore_index=True)
        merged = merged.drop_duplicates(subset=["patient_id", "timestamp"])
        _WEARABLE_CACHE[pid] = merged
        # Update twin state
        from twin.state import update_twin_state
        update_twin_state(pid, merged, db_path=TWIN_DB)
        updated.append(pid)

    return {"accepted": len(payload.readings), "patients_updated": updated}


@router.get("/patients")
def list_gt_patients(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
):
    """List synthetic T2D patients."""
    patients = _load_patients()
    items = list(patients.values())

    if search:
        s = search.lower()
        items = [p for p in items if s in p.get("patient_id", "").lower()]

    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start: start + page_size]

    # Serialise numpy types
    def _clean(p: dict) -> dict:
        return {k: (bool(v) if isinstance(v, (np.bool_,)) else
                    (int(v) if isinstance(v, (np.integer,)) else
                     (float(v) if isinstance(v, (np.floating,)) else v)))
                for k, v in p.items()}

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_clean(p) for p in page_items],
    }


@router.get("/patients/{patient_id}/cgm")
def get_cgm(
    patient_id: str,
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts:   Optional[datetime] = Query(None, alias="to"),
    _current_user: User = Depends(get_current_user),
):
    """Return recent CGM readings for a patient."""
    _get_patient_or_404(patient_id)
    wdf = _load_wearable(patient_id)
    if wdf is None or wdf.empty:
        return {"patient_id": patient_id, "readings": []}

    wdf = wdf.copy()
    wdf["timestamp"] = pd.to_datetime(wdf["timestamp"], utc=True)

    if from_ts:
        from_ts_aware = from_ts.replace(tzinfo=timezone.utc) if from_ts.tzinfo is None else from_ts
        wdf = wdf[wdf["timestamp"] >= from_ts_aware]
    if to_ts:
        to_ts_aware = to_ts.replace(tzinfo=timezone.utc) if to_ts.tzinfo is None else to_ts
        wdf = wdf[wdf["timestamp"] <= to_ts_aware]

    wdf = wdf.sort_values("timestamp").tail(2016)  # cap at 7 days of 5-min data

    def _safe_float(v):
        if v is None:
            return None
        try:
            f = float(v)
            return None if (f != f) else f  # isnan check
        except (TypeError, ValueError):
            return None

    readings = [
        {
            "timestamp": row["timestamp"].isoformat(),
            "glucose_mg_dl": _safe_float(row.get("glucose_mg_dl")),
            "heart_rate": _safe_float(row.get("heart_rate")),
            "hrv_rmssd": _safe_float(row.get("hrv_rmssd")),
            "steps": _safe_float(row.get("steps")),
            "sleep_stage": int(row.get("sleep_stage", 0)) if row.get("sleep_stage") is not None else None,
        }
        for _, row in wdf.iterrows()
    ]
    return {"patient_id": patient_id, "readings": readings}


@router.get("/twin/{patient_id}", response_model=TwinStateOut)
def get_twin(
    patient_id: str,
    _current_user: User = Depends(get_current_user),
):
    """Return current twin state + latest prediction + investigation suggestions."""
    (get_twin_state, save_audit_entry, save_prediction, get_audit_log, init_db,
     predict_row, ModelNotTrainedError, explain_row, evaluate_rules) = _import_twin()
    init_db(TWIN_DB)
    _get_patient_or_404(patient_id)

    state = get_twin_state(patient_id, TWIN_DB)
    if state is None:
        # Initialise from wearable data if available
        wdf = _load_wearable(patient_id)
        if wdf is not None:
            from twin.state import update_twin_state
            state = update_twin_state(patient_id, wdf, db_path=TWIN_DB)
        else:
            state = {
                "patient_id": patient_id,
                "updated_at": None,
                "latest_reading_time": None,
                "time_in_range_7d": None,
                "hypo_events_14d": 0,
                "avg_sleep_h": None,
                "steps_today": None,
                "hrv_trend": 0,
                "last_hba1c_date": None,
                "last_egfr_date": None,
                "last_lipid_date": None,
                "last_eye_date": None,
                "last_foot_date": None,
                "last_prediction_hyper": None,
                "last_prediction_hypo": None,
                "data_gap_flag": 1,
                "confidence_flag": "missing_data",
            }

    # Attach latest prediction
    pred_dict: Optional[dict] = None
    try:
        patient = _get_patient_or_404(patient_id)
        wdf = _load_wearable(patient_id)
        if wdf is not None:
            feature_dict = _build_feature_dict(patient, wdf)
            if feature_dict is not None:
                pred_dict = predict_row(feature_dict)
                pred_dict["top_factors_hyper"] = explain_row(feature_dict, "hyper")
                pred_dict["top_factors_hypo"] = explain_row(feature_dict, "hypo")
    except Exception:
        import logging
        logging.exception("GlucoTwin prediction failed for patient %s", patient_id)

    # Investigation suggestions
    active_high_risk = False
    if pred_dict:
        active_high_risk = (
            pred_dict.get("risk_band_hyper") == "high"
            or pred_dict.get("risk_band_hypo") == "high"
        )
    investigations = evaluate_rules(state, active_high_risk=active_high_risk)

    out = {
        **state,
        "data_gap_flag": bool(state.get("data_gap_flag", 0)),
        "confidence_flag": state.get("confidence_flag", "ok") or "ok",
        "prediction": pred_dict,
        "investigations": investigations,
    }
    return out


@router.get("/predict/{patient_id}", response_model=PredictionOut)
def predict(
    patient_id: str,
    _current_user: User = Depends(get_current_user),
):
    """Return fresh glycaemia prediction + SHAP explanations."""
    (get_twin_state, save_audit_entry, save_prediction, get_audit_log, init_db,
     predict_row, ModelNotTrainedError, explain_row, evaluate_rules) = _import_twin()
    init_db(TWIN_DB)
    patient = _get_patient_or_404(patient_id)
    wdf = _load_wearable(patient_id)

    if wdf is None or wdf.empty:
        raise HTTPException(status_code=404, detail="No wearable data available for this patient")

    feature_dict = _build_feature_dict(patient, wdf)
    if feature_dict is None:
        raise HTTPException(status_code=422, detail="Insufficient data to compute features (need ≥ 6 h of CGM)")

    try:
        pred = predict_row(feature_dict)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    factors_hyper = explain_row(feature_dict, "hyper")
    factors_hypo  = explain_row(feature_dict, "hypo")

    state = get_twin_state(patient_id, TWIN_DB) or {}
    confidence = state.get("confidence_flag", "ok") or "ok"

    # Persist prediction
    save_prediction(
        patient_id,
        forecast_time=datetime.now(timezone.utc).isoformat(),
        p_hyper=pred["p_hyper_120"] or 0.0,
        p_hypo=pred["p_hypo_120"] or 0.0,
        top_factors_hyper=factors_hyper,
        top_factors_hypo=factors_hypo,
        model_version=pred["model_version"],
        db_path=TWIN_DB,
    )

    return {
        "patient_id":        patient_id,
        "p_hyper_120":       pred.get("p_hyper_120"),
        "p_hypo_120":        pred.get("p_hypo_120"),
        "risk_band_hyper":   pred.get("risk_band_hyper", "unknown"),
        "risk_band_hypo":    pred.get("risk_band_hypo", "unknown"),
        "top_factors_hyper": factors_hyper,
        "top_factors_hypo":  factors_hypo,
        "model_version":     pred["model_version"],
        "confidence_flag":   confidence,
    }


@router.get("/investigations/{patient_id}")
def get_investigations(
    patient_id: str,
    _current_user: User = Depends(get_current_user),
):
    """Return rule-based investigation suggestions for a patient."""
    (get_twin_state, save_audit_entry, save_prediction, get_audit_log, init_db,
     predict_row, ModelNotTrainedError, explain_row, evaluate_rules) = _import_twin()
    init_db(TWIN_DB)
    _get_patient_or_404(patient_id)
    state = get_twin_state(patient_id, TWIN_DB) or {}
    suggestions = evaluate_rules(state, active_high_risk=False)
    return {"patient_id": patient_id, "suggestions": suggestions}


@router.post("/decisions", status_code=201)
def record_decision(
    payload: DecisionIn,
    current_user: User = Depends(get_current_user),
):
    """Record a clinician decision (accept / defer / override + reason)."""
    (get_twin_state, save_audit_entry, save_prediction, get_audit_log, init_db,
     predict_row, ModelNotTrainedError, explain_row, evaluate_rules) = _import_twin()
    init_db(TWIN_DB)
    save_audit_entry(
        patient_id      = payload.patient_id,
        suggestion_type = payload.suggestion_type,
        rule_id         = payload.rule_id,
        rule_version    = payload.rule_version,
        decision        = payload.decision,
        reason          = payload.reason,
        model_version   = "lightgbm_v1",
        clinician_id    = str(current_user.id),
        db_path         = TWIN_DB,
    )
    return {"status": "recorded", "patient_id": payload.patient_id, "decision": payload.decision}


@router.get("/audit")
def get_audit(
    patient_id: Optional[str] = Query(None),
    _current_user: User = Depends(get_current_user),
):
    """Return audit log entries."""
    (get_twin_state, save_audit_entry, save_prediction, get_audit_log, init_db,
     predict_row, ModelNotTrainedError, explain_row, evaluate_rules) = _import_twin()
    init_db(TWIN_DB)
    entries = get_audit_log(patient_id, TWIN_DB)
    return {"entries": entries}


@router.post("/demo/advance/{patient_id}")
def demo_advance(
    patient_id: str,
    n_minutes: int = Query(30, ge=5, le=480, description="Minutes of simulated data to replay"),
    _current_user: User = Depends(get_current_user),
):
    """Advance the clearly synthetic demo stream using pre-generated readings."""
    _import_twin()
    _get_patient_or_404(patient_id)

    wdf = _load_wearable(patient_id)
    if wdf is None or wdf.empty:
        raise HTTPException(
            status_code=404,
            detail="No pre-generated synthetic wearable data found for demo replay",
        )

    wdf_sorted = wdf.sort_values("timestamp").reset_index(drop=True).copy()
    n_steps = max(1, n_minutes // 5)
    total = len(wdf_sorted)

    # Start near the end so the first click displays recent synthetic readings.
    cursor = _DEMO_CURSOR.get(patient_id, max(0, total - n_steps))
    if cursor >= total:
        cursor = 0

    end_cursor = min(cursor + n_steps, total)
    batch = wdf_sorted.iloc[cursor:end_cursor].copy()

    # Loop back to the beginning when the prerecorded synthetic sequence ends.
    _DEMO_CURSOR[patient_id] = 0 if end_cursor >= total else end_cursor

    if batch.empty:
        raise HTTPException(status_code=503, detail="Synthetic demo replay produced no readings")

    # Rebase replayed timestamps to the current timeline, preserving 5-minute spacing.
    import pandas as pd
    from datetime import datetime, timezone

    ts = pd.to_datetime(batch["timestamp"], utc=True, errors="coerce")
    valid = ts.dropna()
    if not valid.empty:
        latest_original = valid.max()
        now = pd.Timestamp(datetime.now(timezone.utc))
        batch["timestamp"] = ts + (now - latest_original)

    from twin.state import update_twin_state
    update_twin_state(patient_id, batch, db_path=TWIN_DB)

    glucose = pd.to_numeric(batch["glucose_mg_dl"], errors="coerce").dropna()
    return {
        "patient_id": patient_id,
        "replayed_readings": len(batch),
        "cursor": end_cursor,
        "is_end": end_cursor >= total,
        "data_source": "synthetic_demo",
        "latest_glucose": float(glucose.iloc[-1]) if not glucose.empty else None,
    }
