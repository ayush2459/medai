"""
tests/test_features.py
======================
Tests for the feature engineering module and leakage checks.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from twin.features import (
    ALL_FEATURES,
    GLUCOSE_FEATURES,
    EHR_FEATURES,
    WEARABLE_FEATURES,
    ABLATION_SETS,
    validate_and_impute,
    compute_medians,
    feature_display_name,
)


class TestFeatureColumnDefinitions:
    def test_all_features_non_empty(self):
        assert len(ALL_FEATURES) > 0

    def test_no_duplicate_features(self):
        assert len(ALL_FEATURES) == len(set(ALL_FEATURES))

    def test_ablation_sets_use_valid_features(self):
        for name, feats in ABLATION_SETS.items():
            for f in feats:
                assert f in ALL_FEATURES, f"Ablation set {name} has unknown feature: {f}"

    def test_full_fusion_is_all_features(self):
        assert set(ABLATION_SETS["full_fusion"]) == set(ALL_FEATURES)

    def test_ehr_only_has_no_glucose(self):
        for f in ABLATION_SETS["ehr_only"]:
            assert "glucose" not in f.lower()

    def test_cgm_only_has_no_ehr(self):
        ehr_set = set(EHR_FEATURES)
        for f in ABLATION_SETS["cgm_only"]:
            assert f not in ehr_set


class TestValidateAndImpute:
    def test_fills_missing_columns(self):
        df = pd.DataFrame([{"glucose_current": 110.0}])
        result = validate_and_impute(df)
        for col in ALL_FEATURES:
            assert col in result.columns, f"Missing column after impute: {col}"

    def test_fills_nan_values(self):
        df = pd.DataFrame([{col: np.nan for col in ALL_FEATURES}])
        result = validate_and_impute(df)
        assert not result[ALL_FEATURES].isna().any().any(), "NaNs should be imputed"

    def test_does_not_create_zero_glucose(self):
        """Imputed glucose values should be positive, not zero."""
        df = pd.DataFrame([{col: np.nan for col in ALL_FEATURES}])
        result = validate_and_impute(df)
        assert result["glucose_current"].iloc[0] > 0

    def test_uses_provided_medians(self):
        medians = {col: 999.0 for col in ALL_FEATURES}
        df = pd.DataFrame([{col: np.nan for col in ALL_FEATURES}])
        result = validate_and_impute(df, medians)
        assert result["glucose_current"].iloc[0] == 999.0

    def test_does_not_modify_original(self):
        df = pd.DataFrame([{"glucose_current": 110.0}])
        df_copy = df.copy()
        validate_and_impute(df)
        pd.testing.assert_frame_equal(df, df_copy)


class TestComputeMedians:
    def test_returns_all_feature_medians(self):
        rows = []
        for _ in range(10):
            rows.append({col: np.random.uniform(1, 100) for col in ALL_FEATURES})
        df = pd.DataFrame(rows)
        medians = compute_medians(df)
        for col in ALL_FEATURES:
            assert col in medians

    def test_median_values_correct(self):
        df = pd.DataFrame([{col: float(i) for i, col in enumerate(ALL_FEATURES)}])
        medians = compute_medians(df)
        for i, col in enumerate(ALL_FEATURES):
            assert abs(medians[col] - float(i)) < 1e-6


class TestFeatureDisplayNames:
    def test_all_features_have_display_name(self):
        for col in ALL_FEATURES:
            name = feature_display_name(col)
            assert isinstance(name, str) and len(name) > 0

    def test_known_feature_display(self):
        assert "Current glucose" in feature_display_name("glucose_current")
        assert "Insulin" in feature_display_name("insulin_flag")
        assert "HbA1c" in feature_display_name("hba1c")


class TestNoLeakageInFeatures:
    """
    Verify that the feature columns do not contain direct future information
    (e.g. a 'future_glucose' column).  This is a design check.
    """
    def test_no_future_features(self):
        for col in ALL_FEATURES:
            assert "future" not in col.lower(), f"Suspicious future feature: {col}"
            assert "label" not in col.lower(), f"Suspicious label feature: {col}"
            assert "target" not in col.lower(), f"Suspicious target feature: {col}"
