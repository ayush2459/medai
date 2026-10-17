"""
twin/model_train.py
===================
Train the hyperglycaemia and hypoglycaemia prediction models.

Design choices:
  - Split by patient (70/15/15) — NEVER by time window to prevent leakage.
  - Main model: LightGBM (fast, handles mixed features, works with SHAP).
  - Baselines: persistence, linear extrapolation, logistic regression.
  - Calibration: isotonic regression on the validation set.
  - Ablation: four feature sets (ehr_only, cgm_only, cgm+wearable, full_fusion).
  - Saves calibrated LightGBM bundle to twin/models/glucotwin_{target}_model.pkl

Usage:
  python twin/model_train.py                     # trains on data/dataset.parquet
  python twin/model_train.py --sample            # trains on data/sample/dataset.parquet
  python twin/model_train.py --gru               # also trains optional GRU
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from twin.features import (
    ABLATION_SETS,
    ALL_FEATURES,
    compute_medians,
    validate_and_impute,
)

MODELS_DIR = Path("twin/models")
SEED = 42

# ── Patient-wise split ────────────────────────────────────────────────────────

def split_patients(patient_ids: np.ndarray, seed: int = SEED) -> tuple[list, list, list]:
    """
    Return (train_pids, val_pids, test_pids) split 70/15/15 by patient.
    NEVER splits by time window.
    """
    rng = np.random.default_rng(seed)
    pids = sorted(set(patient_ids))
    rng.shuffle(pids)
    n = len(pids)
    n_val  = max(1, int(n * 0.15))
    n_test = max(1, int(n * 0.15))
    train_pids = pids[:n - n_val - n_test]
    val_pids   = pids[n - n_val - n_test: n - n_test]
    test_pids  = pids[n - n_test:]
    return train_pids, val_pids, test_pids


def assert_no_leakage(
    train_pids: list, val_pids: list, test_pids: list
) -> None:
    """Raise AssertionError if any patient appears in two splits."""
    overlap_tv = set(train_pids) & set(val_pids)
    overlap_tt = set(train_pids) & set(test_pids)
    overlap_vt = set(val_pids)  & set(test_pids)
    assert not overlap_tv, f"Leakage: train∩val = {overlap_tv}"
    assert not overlap_tt, f"Leakage: train∩test = {overlap_tt}"
    assert not overlap_vt, f"Leakage: val∩test = {overlap_vt}"


# ── LightGBM helpers ──────────────────────────────────────────────────────────

def _lgbm_params() -> dict:
    return {
        "objective":   "binary",
        "metric":      "auc",
        "n_estimators": 300,
        "learning_rate": 0.05,
        "num_leaves":    63,
        "max_depth":     -1,
        "min_child_samples": 20,
        "subsample":     0.8,
        "colsample_bytree": 0.8,
        "random_state":  SEED,
        "n_jobs":        -1,
        "verbose":       -1,
    }


def _fit_lgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> lgb.LGBMClassifier:
    """Fit LightGBM with early stopping on validation AUC."""
    clf = lgb.LGBMClassifier(**_lgbm_params())
    clf.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(period=-1)],
    )
    return clf


def _calibrate(clf, X_val: pd.DataFrame, y_val: pd.Series) -> CalibratedClassifierCV:
    """Wrap the fitted classifier with isotonic calibration."""
    cal = CalibratedClassifierCV(clf, method="isotonic", cv="prefit")
    cal.fit(X_val, y_val)
    return cal


# ── Baseline models ───────────────────────────────────────────────────────────

def _persistence_predict(X: pd.DataFrame, threshold: float) -> np.ndarray:
    """Persistence baseline: current glucose > threshold → predict event."""
    return (X["glucose_current"].values > threshold).astype(float)


def _slope_predict(X: pd.DataFrame, threshold: float, lookahead_min: int = 120) -> np.ndarray:
    """Linear extrapolation baseline."""
    slope = X["glucose_slope_15m"].fillna(0).values
    current = X["glucose_current"].values
    projected = current + slope * lookahead_min
    return (projected > threshold).astype(float)


def _logreg_predict(
    X_train: pd.DataFrame, y_train: pd.Series,
    X_test:  pd.DataFrame, features: list[str],
) -> np.ndarray:
    glc_feats = [f for f in features if "glucose" in f and f in X_train.columns]
    if not glc_feats:
        return np.full(len(X_test), y_train.mean())
    lr = LogisticRegression(max_iter=500, random_state=SEED)
    lr.fit(X_train[glc_feats].fillna(0), y_train)
    return lr.predict_proba(X_test[glc_feats].fillna(0))[:, 1]


def _auc_safe(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    return float(roc_auc_score(y_true, y_score))


# ── Training main ─────────────────────────────────────────────────────────────

def train(
    dataset_path: Path = Path("data/dataset.parquet"),
    models_dir: Path = MODELS_DIR,
    train_gru: bool = False,
) -> dict:
    """
    Train both models and return a results dict with split sizes and
    ablation AUROCs (test-set baselines; full metrics in evaluate.py).
    """
    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"[train] Loading dataset from {dataset_path} …")
    df = pd.read_parquet(dataset_path)

    # --- Splits ---
    all_pids = df["patient_id"].values
    train_pids, val_pids, test_pids = split_patients(all_pids)
    assert_no_leakage(train_pids, val_pids, test_pids)

    train_df = df[df["patient_id"].isin(train_pids)]
    val_df   = df[df["patient_id"].isin(val_pids)]
    test_df  = df[df["patient_id"].isin(test_pids)]

    print(
        f"[train] Split: {len(train_pids)} train / {len(val_pids)} val / {len(test_pids)} test patients | "
        f"{len(train_df):,} / {len(val_df):,} / {len(test_df):,} rows"
    )

    # --- Compute medians on training set (no leakage) ---
    train_df_imp = validate_and_impute(train_df)
    medians = compute_medians(train_df_imp)
    val_df_imp   = validate_and_impute(val_df, medians)
    test_df_imp  = validate_and_impute(test_df, medians)

    results: dict = {
        "split": {
            "train_patients": len(train_pids), "val_patients": len(val_pids),
            "test_patients": len(test_pids),
            "train_rows": len(train_df), "val_rows": len(val_df), "test_rows": len(test_df),
        },
        "hyper_event_rate_train": float(train_df["hyper_120"].mean()),
        "hypo_event_rate_train":  float(train_df["hypo_120"].mean()),
        "ablation_auroc_val": {},
    }

    # --- Train both targets ---
    for target, filter_col, filter_val, threshold in [
        ("hyper", "current_glucose", 180.0, 180.0),
        ("hypo",  "current_glucose",  70.0,  70.0),
    ]:
        # Filter: hyper model trained only when current glucose <= threshold
        # hypo model trained only when current glucose >= threshold
        if target == "hyper":
            tr = train_df_imp[train_df_imp["current_glucose"] <= threshold]
            vl = val_df_imp[val_df_imp["current_glucose"] <= threshold]
            te = test_df_imp[test_df_imp["current_glucose"] >= 70.0]  # all except active hypo
        else:
            tr = train_df_imp[train_df_imp["current_glucose"] >= threshold]
            vl = val_df_imp[val_df_imp["current_glucose"] >= threshold]
            te = test_df_imp[test_df_imp["current_glucose"] <= 180.0]  # all except active hyper

        y_tr = tr[f"{target}_120"].astype(int)
        y_vl = vl[f"{target}_120"].astype(int)

        print(f"\n[train] Target: {target}_120  pos_rate_train={y_tr.mean():.1%}  pos_rate_val={y_vl.mean():.1%}")

        X_tr_full = tr[ALL_FEATURES]
        X_vl_full = vl[ALL_FEATURES]
        X_te_full = te[ALL_FEATURES]
        y_te      = te[f"{target}_120"].astype(int)

        # Main LightGBM
        clf = _fit_lgbm(X_tr_full, y_tr, X_vl_full, y_vl)
        cal = _calibrate(clf, X_vl_full, y_vl)

        # Ablation on validation set
        ablation_aucs: dict[str, float | None] = {}
        for abl_name, abl_feats in ABLATION_SETS.items():
            avail = [f for f in abl_feats if f in X_vl_full.columns]
            abl_clf = lgb.LGBMClassifier(**_lgbm_params())
            abl_clf.fit(tr[avail], y_tr,
                        eval_set=[(vl[avail], y_vl)],
                        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(period=-1)])
            proba = abl_clf.predict_proba(X_vl_full[avail])[:, 1]
            ablation_aucs[abl_name] = _auc_safe(y_vl.values, proba)

        results["ablation_auroc_val"][target] = ablation_aucs
        print(f"[train] Ablation val AUROC ({target}): " + " | ".join(
            f"{k}={v:.3f}" for k, v in ablation_aucs.items() if v is not None
        ))

        # Save bundle
        bundle = {
            "calibrated_clf":   cal,
            "base_clf":         clf,
            "feature_columns":  ALL_FEATURES,
            "medians":          medians,
            "target":           f"{target}_120",
            "model_version":    "lightgbm_v1",
            "ablation_auroc_val": ablation_aucs,
        }
        out_path = models_dir / f"glucotwin_{target}_model.pkl"
        with open(out_path, "wb") as f:
            pickle.dump(bundle, f)
        print(f"[train] Saved -> {out_path}")

        # Quick test-set AUROC
        proba_out = cal.predict_proba(X_te_full)
        proba_te = proba_out[:, 1] if proba_out.shape[1] > 1 else proba_out[:, 0]
        test_auc = _auc_safe(y_te.values, proba_te)
        results[f"{target}_auroc_test_quick"] = test_auc
        if test_auc is not None:
            print(f"[train] Quick test AUROC ({target}): {test_auc:.3f}")

    # Save split info for evaluate.py
    with open(models_dir / "patient_splits.json", "w") as f:
        json.dump({
            "train": list(train_pids),
            "val":   list(val_pids),
            "test":  list(test_pids),
        }, f)

    with open(models_dir / "medians.json", "w") as f:
        json.dump(medians, f)

    print(f"\n[train] Done.  Results: {results}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--gru",    action="store_true")
    args = parser.parse_args()
    dataset_path = Path("data/sample/dataset.parquet") if args.sample else Path("data/dataset.parquet")
    train(dataset_path=dataset_path, train_gru=args.gru)
