"""
twin/evaluate.py
================
Full evaluation of the trained models on held-out test patients.

Produces:
  results/metrics.json     – all metrics
  results/ablation.csv     – ablation table
  results/figures/         – ROC, PR, calibration, SHAP summary, lead-time plots

Usage:
  python twin/evaluate.py
  python twin/evaluate.py --sample
"""
from __future__ import annotations

import argparse
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Optional matplotlib / shap
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _PLT = True
except ImportError:
    _PLT = False

try:
    import shap
    _SHAP = True
except ImportError:
    _SHAP = False

from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    auc,
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

import lightgbm as lgb

from twin.features import ABLATION_SETS, ALL_FEATURES, validate_and_impute
from twin.model_train import split_patients, assert_no_leakage, _lgbm_params, SEED

MODELS_DIR = Path("twin/models")
RESULTS_DIR = Path("results")
FIGURES_DIR = RESULTS_DIR / "figures"
ALERT_THRESHOLD = 0.30   # operating point for lead-time calculation

HYPER_THRESHOLD = 180.0
HYPO_THRESHOLD  = 70.0
INTERVAL_MIN    = 5


def _auc_safe(y: np.ndarray, s: np.ndarray) -> float | None:
    if len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, s))


def _auprc_safe(y: np.ndarray, s: np.ndarray) -> float | None:
    if len(np.unique(y)) < 2:
        return None
    return float(average_precision_score(y, s))


def _sens_at_spec(y: np.ndarray, s: np.ndarray, target_spec: float = 0.90) -> float | None:
    if len(np.unique(y)) < 2:
        return None
    fpr, tpr, _ = roc_curve(y, s)
    spec = 1 - fpr
    idx = np.searchsorted(-spec, -target_spec)
    return float(tpr[idx]) if idx < len(tpr) else None


def _mean_lead_time(
    df: pd.DataFrame, probas: np.ndarray, target: str, threshold: float
) -> float | None:
    """
    For each actual event, find the first forecast row exceeding `threshold`
    before the event.  Return mean lead time in minutes.
    """
    if "forecast_time" not in df.columns:
        return None
    df = df.copy()
    df["proba"] = probas
    df["forecast_time"] = pd.to_datetime(df["forecast_time"])
    df = df.sort_values("forecast_time")

    lead_times = []
    # Group by patient; iterate through time
    for pid, grp in df.groupby("patient_id"):
        grp = grp.sort_values("forecast_time").reset_index(drop=True)
        event_idxs = grp.index[grp[target] == 1].tolist()
        for ei in event_idxs:
            # Look back from the event for the first alert
            event_time = grp.loc[ei, "forecast_time"]
            pre = grp[grp["forecast_time"] < event_time]
            alerting = pre[pre["proba"] >= threshold]
            if not alerting.empty:
                first_alert = alerting["forecast_time"].min()
                lead_min = (event_time - first_alert).total_seconds() / 60
                lead_times.append(lead_min)

    return float(np.mean(lead_times)) if lead_times else None


def _compute_metrics(
    y: np.ndarray,
    proba: np.ndarray,
    df_meta: pd.DataFrame,
    target: str,
) -> dict:
    m: dict = {}
    m["auroc"]         = _auc_safe(y, proba)
    m["auprc"]         = _auprc_safe(y, proba)
    m["brier_score"]   = float(brier_score_loss(y, proba)) if len(np.unique(y)) >= 2 else None
    m["sens_at_90spec"]= _sens_at_spec(y, proba, 0.90)
    m["mean_lead_time_min"] = _mean_lead_time(df_meta, proba, target, ALERT_THRESHOLD)
    m["positive_rate"] = float(y.mean())
    m["n_samples"]     = int(len(y))

    # Check for suspicious perfection → leakage warning
    if m["auroc"] is not None and m["auroc"] > 0.99:
        m["leakage_warning"] = (
            f"AUROC={m['auroc']:.4f} is suspiciously high. "
            "Inspect for label leakage. Check that forecast_time is strictly before event onset."
        )
        print(f"[evaluate] WARNING: {m['leakage_warning']}")

    return m


def _stratified_metrics(
    df: pd.DataFrame, proba: np.ndarray, target: str
) -> dict:
    """Return metrics stratified by medication, age band, HbA1c band."""
    strat: dict = {}
    df = df.copy()
    df["proba"] = proba

    # Medication group
    for med_grp, mask_fn in [
        ("insulin_or_su",  lambda d: (d["insulin_flag"] > 0.5) | (d["sulfonylurea_flag"] > 0.5)),
        ("other",          lambda d: (d["insulin_flag"] <= 0.5) & (d["sulfonylurea_flag"] <= 0.5)),
    ]:
        mask = mask_fn(df)
        sub = df[mask]
        if len(sub) > 0 and len(sub[target].unique()) == 2:
            strat[f"med_{med_grp}"] = {
                "auroc": _auc_safe(sub[target].values, sub["proba"].values),
                "n":     int(mask.sum()),
            }

    # Age bands
    for lo, hi, label in [(0, 50, "lt50"), (50, 65, "50_65"), (65, 200, "gt65")]:
        mask = (df["age"] >= lo) & (df["age"] < hi)
        sub = df[mask]
        if len(sub) > 0 and len(sub[target].unique()) == 2:
            strat[f"age_{label}"] = {
                "auroc": _auc_safe(sub[target].values, sub["proba"].values),
                "n":     int(mask.sum()),
            }

    # HbA1c bands
    for lo, hi, label in [(0, 7.5, "lt7.5"), (7.5, 9.0, "7.5_9"), (9.0, 99, "gt9")]:
        mask = (df["hba1c"] >= lo) & (df["hba1c"] < hi)
        sub = df[mask]
        if len(sub) > 0 and len(sub[target].unique()) == 2:
            strat[f"hba1c_{label}"] = {
                "auroc": _auc_safe(sub[target].values, sub["proba"].values),
                "n":     int(mask.sum()),
            }

    return strat


def _plot_roc_pr(y: np.ndarray, proba: np.ndarray, target: str) -> None:
    if not _PLT:
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    fpr, tpr, _ = roc_curve(y, proba)
    ax1.plot(fpr, tpr, lw=2)
    ax1.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax1.set_xlabel("FPR")
    ax1.set_ylabel("TPR")
    ax1.set_title(f"ROC — {target} (AUC={_auc_safe(y, proba):.3f})")

    prec, rec, _ = precision_recall_curve(y, proba)
    ax2.plot(rec, prec, lw=2)
    ax2.set_xlabel("Recall")
    ax2.set_ylabel("Precision")
    ax2.set_title(f"PR — {target}")

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / f"roc_pr_{target}.png", dpi=120)
    plt.close()


def _plot_calibration(y: np.ndarray, proba: np.ndarray, target: str) -> None:
    if not _PLT:
        return
    fraction_pos, mean_pred = calibration_curve(y, proba, n_bins=10)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(mean_pred, fraction_pos, "o-", lw=2)
    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction positive")
    ax.set_title(f"Calibration — {target}")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / f"calibration_{target}.png", dpi=120)
    plt.close()


def _plot_shap_summary(bundle: dict, X: pd.DataFrame, target: str) -> None:
    if not _SHAP or not _PLT:
        return
    base_clf = bundle["base_clf"]
    explainer = shap.TreeExplainer(base_clf, check_additivity=False)
    sample = X.sample(min(500, len(X)), random_state=SEED)
    shap_values = explainer.shap_values(sample, check_additivity=False)
    if isinstance(shap_values, list):
        sv = shap_values[1]
    else:
        sv = shap_values
    fig, ax = plt.subplots(figsize=(7, 6))
    feature_names = bundle["feature_columns"]
    mean_abs = np.abs(sv).mean(axis=0)
    sorted_idx = np.argsort(mean_abs)[-15:]
    ax.barh([feature_names[i] for i in sorted_idx], mean_abs[sorted_idx])
    ax.set_xlabel("|SHAP value| (mean)")
    ax.set_title(f"Feature importance (SHAP) — {target}")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / f"shap_summary_{target}.png", dpi=120)
    plt.close()


def _ablation_table(
    tr_df: pd.DataFrame, y_tr: pd.Series,
    te_df: pd.DataFrame, y_te: pd.Series,
    target: str,
) -> pd.DataFrame:
    rows = []
    for abl_name, abl_feats in ABLATION_SETS.items():
        avail = [f for f in abl_feats if f in tr_df.columns]
        clf = lgb.LGBMClassifier(**_lgbm_params())
        clf.fit(tr_df[avail], y_tr, callbacks=[lgb.log_evaluation(period=-1)])
        proba = clf.predict_proba(te_df[avail])[:, 1]
        auroc = _auc_safe(y_te.values, proba)
        auprc = _auprc_safe(y_te.values, proba)
        rows.append({
            "target":     target,
            "model":      abl_name,
            "auroc_test": auroc,
            "auprc_test": auprc,
        })
    return pd.DataFrame(rows)


def evaluate(
    dataset_path: Path = Path("data/dataset.parquet"),
) -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[evaluate] Loading {dataset_path} …")
    df = pd.read_parquet(dataset_path)

    # Reload splits from training
    splits_path = MODELS_DIR / "patient_splits.json"
    if splits_path.exists():
        with open(splits_path) as f:
            splits = json.load(f)
        train_pids = splits["train"]
        val_pids   = splits["val"]
        test_pids  = splits["test"]
    else:
        train_pids, val_pids, test_pids = split_patients(df["patient_id"].values)
    assert_no_leakage(train_pids, val_pids, test_pids)

    medians_path = MODELS_DIR / "medians.json"
    if medians_path.exists():
        with open(medians_path) as f:
            medians = json.load(f)
    else:
        from twin.features import compute_medians
        train_df = df[df["patient_id"].isin(train_pids)]
        train_df_imp = validate_and_impute(train_df)
        medians = compute_medians(train_df_imp)

    test_df  = df[df["patient_id"].isin(test_pids)]
    train_df = df[df["patient_id"].isin(train_pids)]

    all_metrics: dict = {"model_version": "lightgbm_v1"}
    ablation_frames = []

    for target, filt_col, filt_val in [
        ("hyper", "current_glucose", 180.0),
        ("hypo",  "current_glucose",  70.0),
    ]:
        model_path = MODELS_DIR / f"glucotwin_{target}_model.pkl"
        if not model_path.exists():
            print(f"[evaluate] Model not found: {model_path} — skipping {target}")
            continue

        with open(model_path, "rb") as f:
            bundle = pickle.load(f)

        # Filter test set
        if target == "hyper":
            te = test_df[test_df["current_glucose"] <= filt_val].copy()
            tr = train_df[train_df["current_glucose"] <= filt_val].copy()
        else:
            te = test_df[test_df["current_glucose"] >= filt_val].copy()
            tr = train_df[train_df["current_glucose"] >= filt_val].copy()

        te_imp = validate_and_impute(te, medians)
        tr_imp = validate_and_impute(tr, medians)

        y_te = te[f"{target}_120"].astype(int)
        y_tr = tr[f"{target}_120"].astype(int)

        X_te = te_imp[ALL_FEATURES]
        X_tr = tr_imp[ALL_FEATURES]

        if len(np.unique(y_te)) < 2:
            print(f"[evaluate] Only one class in test set for {target} — skipping detailed metrics")
            continue

        proba = bundle["calibrated_clf"].predict_proba(X_te)[:, 1]

        metrics = _compute_metrics(y_te.values, proba, te_imp, f"{target}_120")
        metrics["stratified"] = _stratified_metrics(te_imp, proba, f"{target}_120")

        all_metrics[target] = metrics

        # Plots
        _plot_roc_pr(y_te.values, proba, target)
        _plot_calibration(y_te.values, proba, target)
        _plot_shap_summary(bundle, X_te, target)

        # Ablation table
        abl_df = _ablation_table(tr_imp, y_tr, te_imp, y_te, target)
        ablation_frames.append(abl_df)

        print(
            f"[evaluate] {target}: AUROC={metrics['auroc']:.3f}  "
            f"AUPRC={metrics['auprc']:.3f}  "
            f"Brier={metrics['brier_score']:.3f}  "
            f"Lead={metrics['mean_lead_time_min']:.1f}min"
            if all(metrics.get(k) is not None for k in ("auroc", "auprc", "brier_score", "mean_lead_time_min"))
            else f"[evaluate] {target}: computed (some values None)"
        )

    # Baselines
    te_imp_full = validate_and_impute(test_df, medians)
    for target, threshold in [("hyper", HYPER_THRESHOLD), ("hypo", HYPO_THRESHOLD)]:
        if target == "hyper":
            sub = te_imp_full[te_imp_full["current_glucose"] <= threshold]
        else:
            sub = te_imp_full[te_imp_full["current_glucose"] >= threshold]
        y = sub[f"{target}_120"].astype(int)
        if len(np.unique(y)) < 2:
            continue

        baseline_key = f"{target}_baselines"
        all_metrics[baseline_key] = {}

        # Persistence
        persist_proba = ((sub["glucose_current"] > threshold).astype(float)
                         if target == "hyper"
                         else (sub["glucose_current"] < threshold).astype(float))
        all_metrics[baseline_key]["persistence"] = {
            "auroc": _auc_safe(y.values, persist_proba.values),
        }

        # Linear extrapolation
        slope = sub["glucose_slope_15m"].fillna(0)
        projected = sub["glucose_current"] + slope * 120
        slope_proba = ((projected > threshold).astype(float)
                       if target == "hyper"
                       else (projected < threshold).astype(float))
        all_metrics[baseline_key]["linear_extrapolation"] = {
            "auroc": _auc_safe(y.values, slope_proba.values),
        }

    # Save
    metrics_path = RESULTS_DIR / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)
    print(f"[evaluate] Saved → {metrics_path}")

    if ablation_frames:
        abl_all = pd.concat(ablation_frames, ignore_index=True)
        abl_path = RESULTS_DIR / "ablation.csv"
        abl_all.to_csv(abl_path, index=False)
        print(f"[evaluate] Saved → {abl_path}")

    return all_metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true")
    args = parser.parse_args()
    data_path = Path("data/sample/dataset.parquet") if args.sample else Path("data/dataset.parquet")
    evaluate(dataset_path=data_path)
