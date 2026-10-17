"""
twin/explain.py
===============
SHAP-based per-prediction explanation of the top contributing factors.

Uses shap.TreeExplainer on the base LightGBM model (unwrapped from the
CalibratedClassifierCV wrapper).

Returns top-5 human-readable factor strings per prediction, e.g.:
  "Glucose rising 2.1 mg/dL per min"
  "Sulfonylurea use"
  "Current glucose 165 mg/dL"
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from twin.features import feature_display_name, validate_and_impute
from twin.predict import MODELS_DIR, _load_model

try:
    import shap
    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False


@lru_cache(maxsize=4)
def _get_explainer(target: str) -> Any:
    """Return a cached SHAP TreeExplainer for the given target."""
    if not _SHAP_AVAILABLE:
        raise ImportError("shap is not installed.  Run: pip install shap")
    bundle = _load_model(target)
    # Unwrap CalibratedClassifierCV → get the base estimator
    base_clf = bundle["base_clf"]
    explainer = shap.TreeExplainer(base_clf, check_additivity=False)
    return explainer, bundle


def explain_row(feature_dict: dict, target: str = "hyper", top_n: int = 5) -> list[str]:
    """
    Compute SHAP values for a single prediction and return top-N human-readable
    factor strings ordered by absolute contribution.

    Parameters
    ----------
    feature_dict : dict of feature name → value for ONE forecast time-point
    target       : "hyper" or "hypo"
    top_n        : number of factors to return

    Returns
    -------
    List of readable strings, e.g. ["Glucose rising 2.1 mg/dL per min", ...]
    Falls back to feature importance ranking if shap is unavailable.
    """
    bundle = _load_model(target)
    medians = bundle["medians"]
    feat_cols = bundle["feature_columns"]

    df = pd.DataFrame([feature_dict])
    df = validate_and_impute(df, medians)
    X = df[feat_cols]

    if not _SHAP_AVAILABLE:
        # Fallback: use model feature importances
        importances = bundle["base_clf"].feature_importances_
        ranked = sorted(zip(feat_cols, importances), key=lambda x: x[1], reverse=True)
        return [_format_factor(col, float(X[col].iloc[0]), None) for col, _ in ranked[:top_n]]

    explainer, _ = _get_explainer(target)
    shap_values = explainer.shap_values(X, check_additivity=False)
    # shap_values shape: (1, n_features) or list[ndarray] for multi-output
    if isinstance(shap_values, list):
        sv = shap_values[1][0]  # class=1 SHAP values for first row
    else:
        sv = shap_values[0]

    sorted_idx = np.argsort(np.abs(sv))[::-1]
    factors = []
    for i in sorted_idx[:top_n]:
        col = feat_cols[i]
        val = float(X[col].iloc[0])
        shap_val = float(sv[i])
        factors.append(_format_factor(col, val, shap_val))

    return factors


def _format_factor(col: str, value: float, shap_val: float | None) -> str:
    """Format a feature + value into a human-readable string."""
    direction = ""
    if shap_val is not None:
        direction = " ↑" if shap_val > 0 else " ↓"

    display = feature_display_name(col)

    # Customise by feature type for more informative messages
    if col == "glucose_current":
        return f"Current glucose {value:.0f} mg/dL{direction}"
    if col == "glucose_slope_15m":
        rate = value * 15  # convert mg/dL/min to mg/dL per 15 min
        dir_str = "rising" if rate > 0 else "falling"
        return f"Glucose {dir_str} {abs(rate):.1f} mg/dL in 15 min{direction}"
    if col == "glucose_slope_30m":
        rate = value * 30
        dir_str = "rising" if rate > 0 else "falling"
        return f"Glucose {dir_str} {abs(rate):.1f} mg/dL in 30 min{direction}"
    if col == "insulin_flag":
        return "Insulin use" + direction if value > 0.5 else "No insulin"
    if col == "sulfonylurea_flag":
        return "Sulfonylurea use" + direction if value > 0.5 else "No sulfonylurea"
    if col == "hba1c":
        return f"HbA1c {value:.1f}%{direction}"
    if col == "sleep_duration_prev_night_h":
        return f"Previous night sleep {value:.1f} h{direction}"
    if col == "steps_30min":
        return f"Steps last 30 min: {value:.0f}{direction}"
    if col == "area_above_140_2h":
        return f"Time above 140 mg/dL (2 h): {value:.0f} mg·min/dL{direction}"
    if col == "glucose_mean_6h":
        return f"Mean glucose last 6 h: {value:.0f} mg/dL{direction}"
    if col == "hrv_now":
        return f"HRV (RMSSD) {value:.0f} ms{direction}"
    # Generic fallback
    return f"{display}: {value:.2g}{direction}"
