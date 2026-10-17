"""
tests/test_state.py
===================
Unit tests for the twin state module.
"""
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from twin.state import (
    init_db,
    update_twin_state,
    get_twin_state,
    save_audit_entry,
    get_audit_log,
    _count_episodes,
)


def _make_wearable(n_days: int = 7, has_hypos: bool = False) -> pd.DataFrame:
    """Create a minimal synthetic wearable DataFrame."""
    start = datetime.now(timezone.utc) - timedelta(days=n_days)
    timestamps = [start + timedelta(minutes=i * 5) for i in range(n_days * 288)]
    n = len(timestamps)
    rng = np.random.default_rng(42)

    glucose = rng.normal(120, 20, n)
    if has_hypos:
        # inject 3 hypo events
        for i in [100, 500, 1200]:
            glucose[i:i+10] = 60.0

    steps = rng.exponential(10, n).astype(np.float32)
    hrv = rng.normal(35, 8, n).astype(np.float32)
    sleep = rng.choice([0, 1, 2, 3], n, p=[0.65, 0.2, 0.1, 0.05]).astype(np.int8)

    return pd.DataFrame({
        "patient_id":        "SYN-TEST",
        "timestamp":         timestamps,
        "glucose_mg_dl":     glucose,
        "heart_rate":        rng.normal(70, 10, n).astype(np.float32),
        "hrv_rmssd":         hrv,
        "steps":             steps,
        "sleep_stage":       sleep,
        "sensor_quality_flag": 1,
    })


class TestTwinStateInit:
    def test_init_creates_tables(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        init_db(db_path)
        # Should not raise
        assert db_path.exists()

    def test_get_nonexistent_returns_none(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        init_db(db_path)
        result = get_twin_state("SYN-NONEXISTENT", db_path)
        assert result is None


class TestUpdateTwinState:
    def test_update_creates_state(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        wdf = _make_wearable(7)
        state = update_twin_state("SYN-TEST", wdf, db_path=db_path)
        assert state["patient_id"] == "SYN-TEST"

    def test_state_has_required_fields(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        wdf = _make_wearable(7)
        state = update_twin_state("SYN-TEST", wdf, db_path=db_path)
        required = {
            "patient_id", "updated_at", "time_in_range_7d",
            "hypo_events_14d", "data_gap_flag", "confidence_flag",
        }
        assert required.issubset(set(state.keys()))

    def test_tir_in_valid_range(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        wdf = _make_wearable(7)
        state = update_twin_state("SYN-TEST", wdf, db_path=db_path)
        if state["time_in_range_7d"] is not None:
            assert 0.0 <= state["time_in_range_7d"] <= 1.0

    def test_detects_data_gap(self):
        """Empty wearable data should set data_gap_flag."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        empty_wdf = pd.DataFrame()
        state = update_twin_state("SYN-TEST", empty_wdf, db_path=db_path)
        assert state["data_gap_flag"] == 1

    def test_hypo_count_increases_with_events(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        wdf_no_hypo = _make_wearable(14, has_hypos=False)
        state_no_hypo = update_twin_state("SYN-TEST", wdf_no_hypo, db_path=db_path)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f2:
            db_path2 = Path(f2.name)
        wdf_hypo = _make_wearable(14, has_hypos=True)
        state_hypo = update_twin_state("SYN-TEST-HYPO", wdf_hypo, db_path=db_path2)

        assert (state_hypo["hypo_events_14d"] or 0) >= (state_no_hypo["hypo_events_14d"] or 0)

    def test_overwrite_updates_existing(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        wdf = _make_wearable(7)
        update_twin_state("SYN-TEST", wdf, db_path=db_path)
        # Update again with new data
        wdf2 = _make_wearable(7)
        state2 = update_twin_state("SYN-TEST", wdf2, db_path=db_path)
        assert state2["patient_id"] == "SYN-TEST"

    def test_get_returns_saved_state(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        wdf = _make_wearable(7)
        update_twin_state("SYN-TEST", wdf, db_path=db_path)
        retrieved = get_twin_state("SYN-TEST", db_path)
        assert retrieved is not None
        assert retrieved["patient_id"] == "SYN-TEST"


class TestAuditLog:
    def test_save_and_retrieve(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        init_db(db_path)
        save_audit_entry(
            patient_id="SYN-TEST",
            suggestion_type="HbA1c recency check",
            rule_id="R1",
            rule_version="1.0",
            decision="defer",
            reason="Patient away",
            model_version="lightgbm_v1",
            clinician_id="doc-123",
            db_path=db_path,
        )
        entries = get_audit_log("SYN-TEST", db_path)
        assert len(entries) == 1
        assert entries[0]["decision"] == "defer"
        assert entries[0]["rule_id"] == "R1"

    def test_invalid_decision_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        init_db(db_path)
        with pytest.raises(AssertionError):
            save_audit_entry(
                patient_id="SYN-TEST",
                suggestion_type="HbA1c",
                rule_id="R1",
                rule_version="1.0",
                decision="invalid_decision",
                reason=None,
                model_version=None,
                clinician_id=None,
                db_path=db_path,
            )


class TestCountEpisodes:
    def test_no_hypo_events(self):
        values = np.array([100.0, 110.0, 120.0, 115.0])
        assert _count_episodes(values, 70.0, below=True) == 0

    def test_single_episode(self):
        values = np.array([100.0, 65.0, 60.0, 58.0, 80.0, 85.0, 90.0, 95.0, 100.0])
        assert _count_episodes(values, 70.0, below=True) == 1

    def test_two_separate_episodes(self):
        # Episode 1: readings 1-4, return to safe for 3+ readings, Episode 2: reading 8-11
        values = np.array([
            65.0, 60.0, 62.0,        # episode 1
            80.0, 85.0, 90.0,        # safe zone (3 readings)
            65.0, 60.0, 58.0,        # episode 2
            90.0, 95.0, 100.0,       # back to safe
        ])
        assert _count_episodes(values, 70.0, below=True) == 2

    def test_nan_values_ignored(self):
        values = np.array([np.nan, 65.0, 60.0, np.nan, 90.0, 95.0, 100.0])
        assert _count_episodes(values, 70.0, below=True) == 1
