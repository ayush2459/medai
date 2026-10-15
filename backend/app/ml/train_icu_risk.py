"""
Trains the ICU admission risk model from AdmissionEvent history in the database
and saves it to app/ml/models/icu_risk_model.joblib.

Usage:
    python3 -m app.ml.train_icu_risk
"""
import joblib
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from app.db.session import SessionLocal
from app.ml.features import FEATURE_COLUMNS, build_training_dataframe

MODEL_PATH = "app/ml/models/icu_risk_model.joblib"


def train() -> None:
    db = SessionLocal()
    try:
        df = build_training_dataframe(db)
    finally:
        db.close()

    if len(df) < 30:
        raise SystemExit(
            f"Only {len(df)} admission events found - need at least 30 to train a meaningful model. "
            "Run `python3 -m app.seed` first (or re-seed with a larger cohort)."
        )

    X = df[FEATURE_COLUMNS]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None
    )

    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print(f"Trained on {len(X_train)} rows, evaluated on {len(X_test)} rows.")
    print(f"ICU admission rate in data: {y.mean():.1%}")
    if y_test.nunique() > 1:
        print(f"ROC-AUC: {roc_auc_score(y_test, y_proba):.3f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS}, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    train()
