"""
data/build_dataset.py
=====================
Merges EHR context and wearable time series into a flat feature dataset
ready for model training.  Called after generate_ehr.py and simulate_wearable.py.

Usage:
  python data/build_dataset.py            # uses data/ directory
  python data/build_dataset.py --sample   # uses data/sample/ directory

Output:
  dataset.parquet   – one row per (patient, forecast_time) with all features and labels
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# ── Constants ─────────────────────────────────────────────────────────────────
FORECAST_INTERVAL_MIN = 15   # produce a forecast every 15 minutes
LOOKAHEAD_MIN         = 120  # predict events in the next 120 min
LOOKBACK_MIN          = 360  # 6-hour historical window

INTERVAL_MIN          = 5    # CGM sampling interval
HYPER_THRESHOLD       = 180.0
HYPO_THRESHOLD        = 70.0

# Feature computation uses a rolling 6-hour window (72 readings)
LOOKBACK_STEPS        = LOOKBACK_MIN // INTERVAL_MIN   # 72
LOOKAHEAD_STEPS       = LOOKAHEAD_MIN // INTERVAL_MIN  # 24
FORECAST_EVERY_STEPS  = FORECAST_INTERVAL_MIN // INTERVAL_MIN  # 3


def _build_patient_features(
    patient_row: pd.Series,
    wearable: pd.DataFrame,
) -> pd.DataFrame | None:
    """Build feature rows for one patient."""
    pid = patient_row["patient_id"]
    pw = wearable[wearable["patient_id"] == pid].copy()
    if len(pw) < LOOKBACK_STEPS + LOOKAHEAD_STEPS:
        return None

    pw = pw.sort_values("timestamp").reset_index(drop=True)
    glc = pw["glucose_mg_dl"].values
    hr  = pw["heart_rate"].values
    hrv = pw["hrv_rmssd"].values
    stp = pw["steps"].values
    slp = pw["sleep_stage"].values
    ts  = pw["timestamp"].values

    # Static EHR context (filled for every row)
    ehr = {
        "age":              float(patient_row.get("age", 55)),
        "bmi":              float(patient_row.get("bmi", 27)),
        "diabetes_duration": float(patient_row.get("diabetes_duration_years", 5)),
        "hba1c":            float(patient_row.get("hba1c_latest", 8.0) or 8.0),
        "egfr":             _latest_lab(patient_row, "egfr"),
        "insulin_flag":     float(patient_row.get("insulin_flag", False)),
        "sulfonylurea_flag": float(patient_row.get("sulfonylurea_flag", False)),
        "ckd_stage":        float(patient_row.get("ckd_stage", 0)),
        "hypertension":     float(patient_row.get("hypertension", False)),
        "genetic_risk_score": float(patient_row.get("genetic_risk_score", 0.2)),
    }

    rows = []
    total = len(pw)
    forecast_ticks = range(LOOKBACK_STEPS, total - LOOKAHEAD_STEPS, FORECAST_EVERY_STEPS)

    for t in forecast_ticks:
        window_glc = glc[t - LOOKBACK_STEPS: t]  # past 6 h of glucose
        future_glc = glc[t: t + LOOKAHEAD_STEPS]  # next 2 h of glucose

        current_glc = glc[t - 1]
        if np.isnan(current_glc):
            continue  # skip if current reading is missing

        # Labels
        future_valid = future_glc[~np.isnan(future_glc)]
        if len(future_valid) == 0:
            continue

        hyper_120 = int(future_valid.max() > HYPER_THRESHOLD)
        hypo_120  = int(future_valid.min() < HYPO_THRESHOLD)

        # Glucose features
        feat = _glucose_features(window_glc, current_glc)

        # Wearable features (recent 30 and 120 min)
        feat["hr_now"]          = float(hr[t - 1]) if not np.isnan(hr[t - 1]) else np.nan
        feat["hrv_now"]         = float(hrv[t - 1]) if not np.isnan(hrv[t - 1]) else np.nan
        feat["steps_30min"]     = float(np.nansum(stp[max(0, t - 6): t]))
        feat["steps_120min"]    = float(np.nansum(stp[max(0, t - 24): t]))

        # Previous night sleep
        prev_night_idx_start = max(0, t - LOOKBACK_STEPS)
        sleep_window = slp[prev_night_idx_start: t]
        sleep_minutes = np.sum(sleep_window > 0) * INTERVAL_MIN
        feat["sleep_duration_prev_night_h"] = float(sleep_minutes / 60)
        # Sleep efficiency: time asleep / time in bed (rough: time_in_bed = 8 h assumed)
        feat["sleep_efficiency"]            = float(min(1.0, sleep_minutes / 480))

        # Time features (hour of day)
        hour_of_day = pd.Timestamp(ts[t]).hour + pd.Timestamp(ts[t]).minute / 60
        feat["hour_sin"] = float(np.sin(2 * np.pi * hour_of_day / 24))
        feat["hour_cos"] = float(np.cos(2 * np.pi * hour_of_day / 24))

        # Append EHR context
        feat.update(ehr)

        # Metadata
        feat["patient_id"]    = pid
        feat["forecast_time"] = ts[t]
        feat["current_glucose"] = current_glc
        feat["hyper_120"]     = hyper_120
        feat["hypo_120"]      = hypo_120

        rows.append(feat)

    if not rows:
        return None
    return pd.DataFrame(rows)


def _glucose_features(window: np.ndarray, current: float) -> dict:
    """Compute glucose-derived features from a 6-h window."""
    feat: dict = {}
    feat["glucose_current"] = current

    # Lags at 15, 30, 60, 120 min (3, 6, 12, 24 steps back)
    for lag_min, lag_steps in [(15, 3), (30, 6), (60, 12), (120, 24)]:
        idx = -lag_steps
        val = window[idx] if abs(idx) <= len(window) else np.nan
        feat[f"glucose_lag_{lag_min}m"] = float(val) if not np.isnan(val) else np.nan

    # Slopes
    for slope_min, slope_steps in [(15, 3), (30, 6)]:
        lag_val = feat.get(f"glucose_lag_{slope_min}m", np.nan)
        feat[f"glucose_slope_{slope_min}m"] = (
            (current - lag_val) / slope_min if not np.isnan(lag_val) else np.nan
        )

    # Rolling stats over valid window values
    valid = window[~np.isnan(window)]
    feat["glucose_mean_6h"] = float(np.mean(valid)) if len(valid) > 0 else current
    feat["glucose_sd_6h"]   = float(np.std(valid))  if len(valid) > 1 else 0.0
    feat["glucose_cv_6h"]   = (
        feat["glucose_sd_6h"] / feat["glucose_mean_6h"]
        if feat["glucose_mean_6h"] > 0 else 0.0
    )

    # Area above 140 in last 2 h (24 steps)
    last_2h = window[-24:]
    feat["area_above_140_2h"] = float(np.nansum(np.maximum(0, last_2h - 140)) * INTERVAL_MIN)

    # Overnight minimum (steps 0-72 of today, roughly midnight to 6 h)
    feat["overnight_min"] = float(np.nanmin(window[:12])) if len(window) >= 12 else np.nan

    # Time since last glucose rise (proxy for meal)
    feat["time_since_last_rise_min"] = _time_since_last_rise(window)

    return feat


def _time_since_last_rise(window: np.ndarray) -> float:
    """Minutes since last rapid glucose rise (>2 mg/dL/min slope)."""
    for i in range(len(window) - 1, 0, -1):
        if np.isnan(window[i]) or np.isnan(window[i - 1]):
            continue
        slope = (window[i] - window[i - 1]) / INTERVAL_MIN
        if slope > 2.0:
            return float((len(window) - 1 - i) * INTERVAL_MIN)
    return float(len(window) * INTERVAL_MIN)


def _latest_lab(row: pd.Series, col: str) -> float:
    """Safely extract a numeric field from a patient row."""
    v = row.get(col, np.nan)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    return float(v)


def build_dataset(data_dir: Path) -> pd.DataFrame:
    """Build and return the full feature dataset."""
    patients  = pd.read_parquet(data_dir / "patients_with_flags.parquet")
    wearable  = pd.read_parquet(data_dir / "wearable.parquet")

    # Try to attach latest eGFR to patients from lab_results
    labs_path = data_dir / "lab_results.parquet"
    if labs_path.exists():
        labs = pd.read_parquet(labs_path)
        egfr = (
            labs[labs["test_code"] == "eGFR"]
            .sort_values("performed_date")
            .groupby("patient_id")["value"]
            .last()
            .rename("egfr")
        )
        patients = patients.join(egfr, on="patient_id")

    frames = []
    for _, row in patients.iterrows():
        df = _build_patient_features(row, wearable)
        if df is not None:
            frames.append(df)

    if not frames:
        raise RuntimeError("No feature rows generated — check EHR and wearable data.")

    dataset = pd.concat(frames, ignore_index=True)

    # Report event rates
    print(f"[build_dataset] {len(dataset):,} forecast rows from {len(patients)} patients")
    print(f"  Hyper label rate: {dataset['hyper_120'].mean():.1%}")
    print(f"  Hypo  label rate: {dataset['hypo_120'].mean():.1%}")
    return dataset


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build merged feature dataset")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    data_dir = Path("data/sample") if args.sample else Path("data")
    # Sample wearable needs patients_with_flags; generate inline if missing
    if args.sample and not (data_dir / "patients_with_flags.parquet").exists():
        from generate_ehr import generate_sample, generate
        generate_sample(data_dir)

    dataset = build_dataset(data_dir)
    out_path = Path(args.out) if args.out else data_dir
    out_path.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(out_path / "dataset.parquet", index=False)
    print(f"[build_dataset] Saved → {out_path}/dataset.parquet")
