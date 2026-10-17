"""
tests/test_split.py
===================
Validates the patient-wise train/val/test split.

Key invariant: no patient must appear in two splits.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from twin.model_train import split_patients, assert_no_leakage


class TestPatientSplit:
    def _make_pids(self, n: int) -> np.ndarray:
        return np.array([f"SYN-{i:04d}" for i in range(n)])

    def test_split_covers_all_patients(self):
        pids = self._make_pids(100)
        train, val, test = split_patients(pids)
        all_split = set(train) | set(val) | set(test)
        assert all_split == set(pids)

    def test_no_leakage(self):
        pids = self._make_pids(100)
        train, val, test = split_patients(pids)
        # Should not raise
        assert_no_leakage(train, val, test)

    def test_raises_on_leakage(self):
        train = ["SYN-0001", "SYN-0002"]
        val   = ["SYN-0002", "SYN-0003"]  # SYN-0002 in both
        test  = ["SYN-0004"]
        with pytest.raises(AssertionError):
            assert_no_leakage(train, val, test)

    def test_split_proportions(self):
        pids = self._make_pids(200)
        train, val, test = split_patients(pids)
        n = len(pids)
        # Allow ±2 patients tolerance
        assert abs(len(train) - int(n * 0.70)) <= 2
        assert abs(len(val)   - int(n * 0.15)) <= 2
        assert abs(len(test)  - int(n * 0.15)) <= 2

    def test_reproducible_split(self):
        pids = self._make_pids(100)
        train1, val1, test1 = split_patients(pids, seed=42)
        train2, val2, test2 = split_patients(pids, seed=42)
        assert train1 == train2
        assert val1   == val2
        assert test1  == test2

    def test_minimum_patients(self):
        pids = self._make_pids(6)  # minimum viable
        train, val, test = split_patients(pids)
        assert len(train) >= 1
        assert len(val)   >= 1
        assert len(test)  >= 1
