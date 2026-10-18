"""
twin/predict.py
===============
Load the trained calibrated models and produce predictions for a single
feature vector or a DataFrame.

The bundle loaded from twin/models/glucotwin_{target}_model.pkl contains:
  - calibrated_clf   : CalibratedClassifierCV wrapping the LightGBM model
  - feature_columns  : ordered list of feature names
  - medians          : dict for NaN imputation
  - target           : "hyper_120" or "hypo_120"
  - model_version    : string tag
"""
from __future__ import annotations

import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from twin.features import ALL_FEATURES, validate_and_impute

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODEL_VERSION = "lightgbm_v1"

RISK_BANDS = {
    "high":   0.60,
    "medium": 0.30,
    "low":    0.00,
}


class ModelNotTrainedError(Exception):
    pass


def _band(prob: float) -> str:
    if prob >= 0.60:
        return "high"
    if prob >= 0.30:
        return "medium"
    return "low"


@lru_cache(maxsize=4)
def _load_model(target: str) -> dict:
    path = MODELS_DIR / f"glucotwin_{target}_model.pkl"
    if not path.exists():
        raise ModelNotTrainedError(
            f"Model not found at {path}. Run: python twin/model_train.py"
        )
    with open(path, "rb") as f:
        return pickle.load(f)


def predict_row(feature_dict: dict) -> dict:
    """
    Given a feature dictionary (one forecast time-point for one patient),
    return prediction results for both hyper and hypo targets.

    Returns
    -------
    dict with keys:
        p_hyper_120, p_hypo_120,
        risk_band_hyper, risk_band_hypo,
        model_version
    """
    results = {}
    for target in ("hyper", "hypo"):
        try:
            bundle = _load_model(target)
        except ModelNotTrainedError:
            results[f"p_{target}_120"] = None
            results[f"risk_band_{target}"] = "unknown"
            continue

        medians = bundle["medians"]
        feat_cols = bundle["feature_columns"]

        df = pd.DataFrame([feature_dict])
        df = validate_and_impute(df, medians)
        X = df[feat_cols]

        prob = float(bundle["calibrated_clf"].predict_proba(X)[0, 1])
        results[f"p_{target}_120"] = round(prob, 4)
        results[f"risk_band_{target}"] = _band(prob)

    results["model_version"] = MODEL_VERSION
    return results


def predict_batch(df: pd.DataFrame) -> pd.DataFrame:
    """
    Predict for a DataFrame of feature rows.
    Returns the input DataFrame with added columns:
        p_hyper_120, risk_band_hyper, p_hypo_120, risk_band_hypo, model_version
    """
    out = df.copy()
    for target in ("hyper", "hypo"):
        try:
            bundle = _load_model(target)
        except ModelNotTrainedError:
            out[f"p_{target}_120"] = None
            out[f"risk_band_{target}"] = "unknown"
            continue

        medians = bundle["medians"]
        feat_cols = bundle["feature_columns"]
        df_imp = validate_and_impute(df, medians)
        X = df_imp[feat_cols]
        proba = bundle["calibrated_clf"].predict_proba(X)[:, 1]
        out[f"p_{target}_120"]    = np.round(proba, 4)
        out[f"risk_band_{target}"] = [_band(p) for p in proba]

    out["model_version"] = MODEL_VERSION
    return out


def get_model_version() -> str:
    return MODEL_VERSION
