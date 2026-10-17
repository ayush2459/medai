"""
twin/features.py
================
Feature column definitions and validation helpers shared between training
and inference.  All feature computation for a single forecast time-point
happens in data/build_dataset.py at dataset-build time; this module defines
the canonical ordered column list and input validation / imputation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ── Canonical feature columns (order matters for model serialisation) ──────────

GLUCOSE_FEATURES = [
    "glucose_current",
    "glucose_lag_15m",
    "glucose_lag_30m",
    "glucose_lag_60m",
    "glucose_lag_120m",
    "glucose_slope_15m",
    "glucose_slope_30m",
    "glucose_mean_6h",
    "glucose_sd_6h",
    "glucose_cv_6h",
    "area_above_140_2h",
    "overnight_min",
    "time_since_last_rise_min",
]

WEARABLE_FEATURES = [
    "hr_now",
    "hrv_now",
    "steps_30min",
    "steps_120min",
    "sleep_duration_prev_night_h",
    "sleep_efficiency",
    "hour_sin",
    "hour_cos",
]

EHR_FEATURES = [
    "age",
    "bmi",
    "diabetes_duration",
    "hba1c",
    "egfr",
    "insulin_flag",
    "sulfonylurea_flag",
    "ckd_stage",
    "hypertension",
    "genetic_risk_score",
]

ALL_FEATURES = GLUCOSE_FEATURES + WEARABLE_FEATURES + EHR_FEATURES

# Feature set definitions for ablation study
ABLATION_SETS: dict[str, list[str]] = {
    "ehr_only":       EHR_FEATURES,
    "cgm_only":       GLUCOSE_FEATURES,
    "cgm_wearable":   GLUCOSE_FEATURES + WEARABLE_FEATURES,
    "full_fusion":    ALL_FEATURES,
}

# ── Medians for imputation (will be populated after fitting) ──────────────────
# These defaults are used only as fallbacks when the fitted medians file is absent.
SAFE_DEFAULTS: dict[str, float] = {
    "glucose_current":   110.0,
    "glucose_lag_15m":   108.0,
    "glucose_lag_30m":   106.0,
    "glucose_lag_60m":   104.0,
    "glucose_lag_120m":  102.0,
    "glucose_slope_15m": 0.0,
    "glucose_slope_30m": 0.0,
    "glucose_mean_6h":   110.0,
    "glucose_sd_6h":     18.0,
    "glucose_cv_6h":     0.16,
    "area_above_140_2h": 0.0,
    "overnight_min":     95.0,
    "time_since_last_rise_min": 90.0,
    "hr_now":            72.0,
    "hrv_now":           30.0,
    "steps_30min":       200.0,
    "steps_120min":      600.0,
    "sleep_duration_prev_night_h": 6.5,
    "sleep_efficiency":  0.85,
    "hour_sin":          0.0,
    "hour_cos":          1.0,
    "age":               57.0,
    "bmi":               27.5,
    "diabetes_duration": 7.0,
    "hba1c":             8.0,
    "egfr":              70.0,
    "insulin_flag":      0.0,
    "sulfonylurea_flag": 0.0,
    "ckd_stage":         0.0,
    "hypertension":      0.0,
    "genetic_risk_score": 0.2,
}


def validate_and_impute(df: pd.DataFrame, medians: dict[str, float] | None = None) -> pd.DataFrame:
    """
    Ensure all feature columns are present; fill NaNs with medians or safe defaults.
    Does NOT leak future information.

    Parameters
    ----------
    df      : DataFrame that must contain all feature columns
    medians : Dict of column → median value from the training set.
              If None, SAFE_DEFAULTS are used.

    Returns
    -------
    DataFrame with same rows, all feature columns present and no NaN.
    """
    fallback = medians if medians is not None else SAFE_DEFAULTS
    df = df.copy()

    # Add missing columns with safe defaults (e.g. egfr missing in some patients)
    for col in ALL_FEATURES:
        if col not in df.columns:
            df[col] = fallback.get(col, 0.0)

    # Impute NaNs column by column
    for col in ALL_FEATURES:
        if df[col].isna().any():
            fill_val = fallback.get(col, 0.0)
            df[col] = df[col].fillna(fill_val)

    return df


def compute_medians(df: pd.DataFrame) -> dict[str, float]:
    """Compute per-column medians from a training DataFrame (to pass back to validate_and_impute)."""
    return {col: float(df[col].median()) for col in ALL_FEATURES if col in df.columns}


def feature_display_name(col: str) -> str:
    """Human-readable label for a feature column (for SHAP explanations)."""
    labels = {
        "glucose_current":   "Current glucose",
        "glucose_lag_15m":   "Glucose 15 min ago",
        "glucose_lag_30m":   "Glucose 30 min ago",
        "glucose_lag_60m":   "Glucose 60 min ago",
        "glucose_lag_120m":  "Glucose 120 min ago",
        "glucose_slope_15m": "Glucose slope (15 min)",
        "glucose_slope_30m": "Glucose slope (30 min)",
        "glucose_mean_6h":   "Mean glucose (6 h)",
        "glucose_sd_6h":     "Glucose variability (6 h SD)",
        "glucose_cv_6h":     "Glucose CV (6 h)",
        "area_above_140_2h": "Area above 140 mg/dL (2 h)",
        "overnight_min":     "Overnight glucose minimum",
        "time_since_last_rise_min": "Time since last glucose rise",
        "hr_now":            "Heart rate",
        "hrv_now":           "HRV (RMSSD)",
        "steps_30min":       "Steps (30 min)",
        "steps_120min":      "Steps (120 min)",
        "sleep_duration_prev_night_h": "Previous night sleep (h)",
        "sleep_efficiency":  "Sleep efficiency",
        "hour_sin":          "Hour of day (sin)",
        "hour_cos":          "Hour of day (cos)",
        "age":               "Patient age",
        "bmi":               "BMI",
        "diabetes_duration": "Diabetes duration (years)",
        "hba1c":             "HbA1c (%)",
        "egfr":              "eGFR",
        "insulin_flag":      "Insulin use",
        "sulfonylurea_flag": "Sulfonylurea use",
        "ckd_stage":         "CKD stage",
        "hypertension":      "Hypertension",
        "genetic_risk_score": "Genetic risk score",
    }
    return labels.get(col, col)
