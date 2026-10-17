"""
twin/state.py
=============
Persistent per-patient twin state stored in SQLite (separate from the main
PostgreSQL DB so this module runs without any Postgres dependency).

Schema
------
  twin_state    – one row per patient, updated on every reading batch
  predictions   – one row per (patient_id, forecast_time)
  audit_log     – clinician decisions (accept / defer / override + reason)

The state captures:
  - latest_reading_time
  - time_in_range_7d (% of valid readings in 70–180 mg/dL over last 7 days)
  - hypo_events_14d  (count of hypoglycaemic episodes in last 14 days)
  - avg_sleep_h      (mean sleep hours last 7 nights)
  - steps_today      (cumulative steps in the last 24 h)
  - hrv_trend        (+1 improving, 0 stable, -1 declining over 7 days)
  - last_hba1c_date  (ISO date string or None)
  - last_egfr_date
  - last_lipid_date
  - last_eye_date
  - last_foot_date
  - last_prediction_hyper  (latest p_hyper_120)
  - last_prediction_hypo   (latest p_hypo_120)
  - data_gap_flag    (True if no reading in >30 min)
  - confidence_flag  ("ok" | "low_confidence" | "missing_data")
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

import numpy as np
import pandas as pd

DB_PATH = Path("twin_state.db")

HYPER_THRESHOLD = 180.0
HYPO_THRESHOLD  = 70.0
GAP_MINUTES     = 30   # data gap threshold


# ── DDL ────────────────────────────────────────────────────────────────────────

CREATE_TWIN_STATE = """
CREATE TABLE IF NOT EXISTS twin_state (
    patient_id          TEXT PRIMARY KEY,
    updated_at          TEXT NOT NULL,
    latest_reading_time TEXT,
    time_in_range_7d    REAL,
    hypo_events_14d     INTEGER,
    avg_sleep_h         REAL,
    steps_today         REAL,
    hrv_trend           INTEGER,
    last_hba1c_date     TEXT,
    last_egfr_date      TEXT,
    last_lipid_date     TEXT,
    last_eye_date       TEXT,
    last_foot_date      TEXT,
    last_prediction_hyper REAL,
    last_prediction_hypo  REAL,
    data_gap_flag       INTEGER DEFAULT 0,
    confidence_flag     TEXT DEFAULT 'ok'
);
"""

CREATE_PREDICTIONS = """
CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      TEXT NOT NULL,
    forecast_time   TEXT NOT NULL,
    p_hyper_120     REAL,
    p_hypo_120      REAL,
    risk_band_hyper TEXT,
    risk_band_hypo  TEXT,
    top_factors_hyper TEXT,
    top_factors_hypo  TEXT,
    model_version   TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
"""

CREATE_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      TEXT NOT NULL,
    suggestion_type TEXT NOT NULL,
    rule_id         TEXT,
    rule_version    TEXT,
    decision        TEXT NOT NULL CHECK(decision IN ('accept','defer','override')),
    reason          TEXT,
    model_version   TEXT,
    clinician_id    TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
"""


# ── Connection helper ─────────────────────────────────────────────────────────

def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables if they do not exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_TWIN_STATE)
        conn.execute(CREATE_PREDICTIONS)
        conn.execute(CREATE_AUDIT_LOG)
        conn.commit()


@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── Twin state helpers ────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _risk_band(prob: float | None) -> str:
    if prob is None:
        return "unknown"
    if prob >= 0.6:
        return "high"
    if prob >= 0.3:
        return "medium"
    return "low"


def update_twin_state(
    patient_id: str,
    wearable_df: pd.DataFrame,
    lab_dates: dict[str, str | None] | None = None,
    p_hyper: float | None = None,
    p_hypo:  float | None = None,
    db_path: Path = DB_PATH,
) -> dict:
    """
    Recompute twin state for `patient_id` from the wearable readings in `wearable_df`.

    Parameters
    ----------
    patient_id   : synthetic patient ID (e.g. "SYN-0001")
    wearable_df  : DataFrame with columns [timestamp, glucose_mg_dl, sleep_stage,
                   steps, hrv_rmssd]; only rows for this patient; sorted ascending.
    lab_dates    : dict with optional keys: last_hba1c_date, last_egfr_date,
                   last_lipid_date, last_eye_date, last_foot_date
    p_hyper      : latest hyperglycaemia risk prediction
    p_hypo       : latest hypoglycaemia risk prediction
    db_path      : path to the SQLite file

    Returns the updated state dict.
    """
    if wearable_df.empty:
        return _write_empty_state(patient_id, db_path)

    df = wearable_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp")

    now = datetime.now(timezone.utc)
    latest_ts = df["timestamp"].max()

    # --- Data gap flag ---
    gap_minutes = (now - latest_ts).total_seconds() / 60
    data_gap = gap_minutes > GAP_MINUTES
    confidence = "missing_data" if data_gap else "ok"

    # --- Time in range (last 7 days) ---
    cutoff_7d = now - timedelta(days=7)
    recent_7d = df[df["timestamp"] >= cutoff_7d]["glucose_mg_dl"].dropna()
    if len(recent_7d) > 0:
        tir = float(((recent_7d >= HYPO_THRESHOLD) & (recent_7d <= HYPER_THRESHOLD)).mean())
    else:
        tir = None
        confidence = "low_confidence"

    # --- Hypo events (last 14 days): count distinct episodes ---
    cutoff_14d = now - timedelta(days=14)
    recent_14d = df[df["timestamp"] >= cutoff_14d][["timestamp", "glucose_mg_dl"]].copy()
    hypo_events = _count_episodes(recent_14d["glucose_mg_dl"].values, HYPO_THRESHOLD, below=True)

    # --- Sleep (last 7 days) ---
    if "sleep_stage" in df.columns:
        sleep_7d = df[df["timestamp"] >= cutoff_7d]["sleep_stage"]
        sleep_minutes = float(np.sum(sleep_7d > 0) * 5)  # 5 min per reading
        avg_sleep_h = sleep_minutes / (7 * 24)  # mean per night approximation
        avg_sleep_h = min(12.0, sleep_minutes / 7)
    else:
        avg_sleep_h = None

    # --- Steps today ---
    cutoff_24h = now - timedelta(hours=24)
    if "steps" in df.columns:
        steps_today = float(df[df["timestamp"] >= cutoff_24h]["steps"].sum())
    else:
        steps_today = None

    # --- HRV trend ---
    hrv_trend = 0
    if "hrv_rmssd" in df.columns:
        cutoff_3d_ago = now - timedelta(days=3)
        early = df[(df["timestamp"] >= cutoff_7d) & (df["timestamp"] < cutoff_3d_ago)]["hrv_rmssd"].mean()
        late  = df[df["timestamp"] >= cutoff_3d_ago]["hrv_rmssd"].mean()
        if not (np.isnan(early) or np.isnan(late)):
            hrv_trend = 1 if late > early + 2 else (-1 if late < early - 2 else 0)

    ld = lab_dates or {}

    state = {
        "patient_id":          patient_id,
        "updated_at":          _utcnow(),
        "latest_reading_time": latest_ts.isoformat() if not pd.isnull(latest_ts) else None,
        "time_in_range_7d":    round(tir, 4) if tir is not None else None,
        "hypo_events_14d":     hypo_events,
        "avg_sleep_h":         round(avg_sleep_h, 2) if avg_sleep_h is not None else None,
        "steps_today":         round(steps_today, 0) if steps_today is not None else None,
        "hrv_trend":           hrv_trend,
        "last_hba1c_date":     ld.get("last_hba1c_date"),
        "last_egfr_date":      ld.get("last_egfr_date"),
        "last_lipid_date":     ld.get("last_lipid_date"),
        "last_eye_date":       ld.get("last_eye_date"),
        "last_foot_date":      ld.get("last_foot_date"),
        "last_prediction_hyper": p_hyper,
        "last_prediction_hypo":  p_hypo,
        "data_gap_flag":       int(data_gap),
        "confidence_flag":     confidence,
    }

    with get_conn(db_path) as conn:
        conn.execute("""
            INSERT INTO twin_state (
                patient_id, updated_at, latest_reading_time, time_in_range_7d,
                hypo_events_14d, avg_sleep_h, steps_today, hrv_trend,
                last_hba1c_date, last_egfr_date, last_lipid_date,
                last_eye_date, last_foot_date,
                last_prediction_hyper, last_prediction_hypo,
                data_gap_flag, confidence_flag
            ) VALUES (
                :patient_id, :updated_at, :latest_reading_time, :time_in_range_7d,
                :hypo_events_14d, :avg_sleep_h, :steps_today, :hrv_trend,
                :last_hba1c_date, :last_egfr_date, :last_lipid_date,
                :last_eye_date, :last_foot_date,
                :last_prediction_hyper, :last_prediction_hypo,
                :data_gap_flag, :confidence_flag
            )
            ON CONFLICT(patient_id) DO UPDATE SET
                updated_at              = excluded.updated_at,
                latest_reading_time     = excluded.latest_reading_time,
                time_in_range_7d        = excluded.time_in_range_7d,
                hypo_events_14d         = excluded.hypo_events_14d,
                avg_sleep_h             = excluded.avg_sleep_h,
                steps_today             = excluded.steps_today,
                hrv_trend               = excluded.hrv_trend,
                last_hba1c_date         = excluded.last_hba1c_date,
                last_egfr_date          = excluded.last_egfr_date,
                last_lipid_date         = excluded.last_lipid_date,
                last_eye_date           = excluded.last_eye_date,
                last_foot_date          = excluded.last_foot_date,
                last_prediction_hyper   = excluded.last_prediction_hyper,
                last_prediction_hypo    = excluded.last_prediction_hypo,
                data_gap_flag           = excluded.data_gap_flag,
                confidence_flag         = excluded.confidence_flag
        """, state)
        conn.commit()

    return state


def get_twin_state(patient_id: str, db_path: Path = DB_PATH) -> dict | None:
    """Return the current twin state for a patient, or None if not found."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM twin_state WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    return dict(row) if row else None


def save_prediction(
    patient_id: str,
    forecast_time: str,
    p_hyper: float,
    p_hypo: float,
    top_factors_hyper: list[str],
    top_factors_hypo: list[str],
    model_version: str,
    db_path: Path = DB_PATH,
) -> None:
    """Append a prediction row to the predictions table."""
    with get_conn(db_path) as conn:
        conn.execute("""
            INSERT INTO predictions
                (patient_id, forecast_time, p_hyper_120, p_hypo_120,
                 risk_band_hyper, risk_band_hypo,
                 top_factors_hyper, top_factors_hypo, model_version)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            patient_id,
            forecast_time,
            p_hyper,
            p_hypo,
            _risk_band(p_hyper),
            _risk_band(p_hypo),
            json.dumps(top_factors_hyper),
            json.dumps(top_factors_hypo),
            model_version,
        ))
        conn.commit()


def save_audit_entry(
    patient_id: str,
    suggestion_type: str,
    rule_id: str | None,
    rule_version: str | None,
    decision: str,
    reason: str | None,
    model_version: str | None,
    clinician_id: str | None,
    db_path: Path = DB_PATH,
) -> None:
    """Record a clinician decision."""
    assert decision in ("accept", "defer", "override"), f"Invalid decision: {decision}"
    with get_conn(db_path) as conn:
        conn.execute("""
            INSERT INTO audit_log
                (patient_id, suggestion_type, rule_id, rule_version,
                 decision, reason, model_version, clinician_id)
            VALUES (?,?,?,?,?,?,?,?)
        """, (patient_id, suggestion_type, rule_id, rule_version,
              decision, reason, model_version, clinician_id))
        conn.commit()


def get_audit_log(patient_id: str | None = None, db_path: Path = DB_PATH) -> list[dict]:
    """Return audit log entries, optionally filtered by patient."""
    with get_conn(db_path) as conn:
        if patient_id:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE patient_id = ? ORDER BY created_at DESC",
                (patient_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 200"
            ).fetchall()
    return [dict(r) for r in rows]


# ── Episode counter ───────────────────────────────────────────────────────────

def _count_episodes(values: np.ndarray, threshold: float, below: bool = True) -> int:
    """
    Count distinct hypoglycaemic (or hyperglycaemic) episodes.
    An episode starts when crossing the threshold and ends when we
    return to the safe zone for at least 15 minutes (3 readings).
    """
    in_episode = False
    consecutive_safe = 0
    episodes = 0
    for v in values:
        if np.isnan(v):
            continue
        crossed = (v < threshold) if below else (v > threshold)
        if crossed:
            if not in_episode:
                episodes += 1
                in_episode = True
            consecutive_safe = 0
        else:
            if in_episode:
                consecutive_safe += 1
                if consecutive_safe >= 3:
                    in_episode = False
                    consecutive_safe = 0
    return episodes


def _write_empty_state(patient_id: str, db_path: Path) -> dict:
    state: dict = {
        "patient_id":          patient_id,
        "updated_at":          _utcnow(),
        "latest_reading_time": None,
        "time_in_range_7d":    None,
        "hypo_events_14d":     0,
        "avg_sleep_h":         None,
        "steps_today":         None,
        "hrv_trend":           0,
        "last_hba1c_date":     None,
        "last_egfr_date":      None,
        "last_lipid_date":     None,
        "last_eye_date":       None,
        "last_foot_date":      None,
        "last_prediction_hyper": None,
        "last_prediction_hypo":  None,
        "data_gap_flag":       1,
        "confidence_flag":     "missing_data",
    }
    with get_conn(db_path) as conn:
        conn.execute("""
            INSERT INTO twin_state (
                patient_id, updated_at, latest_reading_time, time_in_range_7d,
                hypo_events_14d, avg_sleep_h, steps_today, hrv_trend,
                last_hba1c_date, last_egfr_date, last_lipid_date,
                last_eye_date, last_foot_date,
                last_prediction_hyper, last_prediction_hypo,
                data_gap_flag, confidence_flag
            ) VALUES (
                :patient_id,:updated_at,:latest_reading_time,:time_in_range_7d,
                :hypo_events_14d,:avg_sleep_h,:steps_today,:hrv_trend,
                :last_hba1c_date,:last_egfr_date,:last_lipid_date,
                :last_eye_date,:last_foot_date,
                :last_prediction_hyper,:last_prediction_hypo,
                :data_gap_flag,:confidence_flag
            ) ON CONFLICT(patient_id) DO UPDATE SET
                updated_at=excluded.updated_at,
                data_gap_flag=1, confidence_flag='missing_data'
        """, state)
        conn.commit()
    return state
