import os
from functools import lru_cache

import joblib
import pandas as pd

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "icu_risk_model.joblib")


class ModelNotTrainedError(Exception):
    pass


@lru_cache
def _load_model():
    if not os.path.exists(MODEL_PATH):
        raise ModelNotTrainedError(
            "No trained model found. Run `python3 -m app.ml.train_icu_risk` from the backend folder first."
        )
    return joblib.load(MODEL_PATH)


def predict_icu_risk(feature_row: dict) -> dict:
    """
    feature_row: dict matching app.ml.features.FEATURE_COLUMNS
    Returns: {"probability": float, "risk_level": str, "top_factors": list[str]}
    """
    bundle = _load_model()
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]

    df = pd.DataFrame([feature_row], columns=feature_columns)
    probability = float(model.predict_proba(df)[0, 1])

    if probability >= 0.66:
        risk_level = "high"
    elif probability >= 0.33:
        risk_level = "medium"
    else:
        risk_level = "low"

    # Simple, honest explanation: which features contributed most for THIS row,
    # using the model's built-in feature importances as a rough weighting.
    # This is not a full SHAP explanation - it's a lightweight approximation
    # good enough for a "why" hint in the UI, not a clinical justification.
    importances = model.feature_importances_
    ranked = sorted(zip(feature_columns, importances), key=lambda x: x[1], reverse=True)
    top_factors = [name for name, _ in ranked[:3]]

    return {
        "probability": round(probability, 4),
        "risk_level": risk_level,
        "top_factors": top_factors,
    }
