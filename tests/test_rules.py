"""
tests/test_rules.py
===================
Unit tests for the rule engine.

Tests all key behaviours:
  - Due, Recent, Missing data states for R1–R4
  - R5 CGM-triggered review (TIR and hypo thresholds)
  - R6 context override
  - Missing data returns "missing_data" status, never a suggestion
"""
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from rules.engine import evaluate_rules, STATUS_DUE, STATUS_RECENT, STATUS_MISSING, STATUS_OK, STATUS_REFER, STATUS_OVERRIDE


def _state(
    last_hba1c_date=None,
    last_egfr_date=None,
    last_lipid_date=None,
    last_eye_date=None,
    last_foot_date=None,
    time_in_range_7d=None,
    hypo_events_14d=0,
):
    return {
        "last_hba1c_date":  last_hba1c_date,
        "last_egfr_date":   last_egfr_date,
        "last_lipid_date":  last_lipid_date,
        "last_eye_date":    last_eye_date,
        "last_foot_date":   last_foot_date,
        "time_in_range_7d": time_in_range_7d,
        "hypo_events_14d":  hypo_events_14d,
        "data_gap_flag":    0,
        "confidence_flag":  "ok",
    }


def _date_str(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


from typing import Optional

def _get_suggestion(suggestions, rule_id: str, check_type: Optional[str] = None) -> Optional[dict]:
    for s in suggestions:
        if s["rule_id"] == rule_id:
            if check_type is None:
                return s
            if s.get("detail", {}).get("check_type") == check_type:
                return s
    return None


class TestR1HbA1c:
    def test_missing_date_returns_missing(self):
        results = evaluate_rules(_state(last_hba1c_date=None))
        s = _get_suggestion(results, "R1")
        assert s is not None
        assert s["status"] == STATUS_MISSING

    def test_recent_date_returns_recent(self):
        results = evaluate_rules(_state(last_hba1c_date=_date_str(30)))
        s = _get_suggestion(results, "R1")
        assert s["status"] == STATUS_RECENT

    def test_old_date_returns_due(self):
        results = evaluate_rules(_state(last_hba1c_date=_date_str(120)))  # 4 months
        s = _get_suggestion(results, "R1")
        assert s["status"] == STATUS_DUE

    def test_message_not_empty(self):
        results = evaluate_rules(_state(last_hba1c_date=_date_str(30)))
        s = _get_suggestion(results, "R1")
        assert len(s["message"]) > 0


class TestR2Kidney:
    def test_missing_returns_missing(self):
        results = evaluate_rules(_state(last_egfr_date=None))
        s = _get_suggestion(results, "R2")
        assert s["status"] == STATUS_MISSING

    def test_recent_within_12_months(self):
        results = evaluate_rules(_state(last_egfr_date=_date_str(180)))  # 6 months
        s = _get_suggestion(results, "R2")
        assert s["status"] == STATUS_RECENT

    def test_old_over_12_months(self):
        results = evaluate_rules(_state(last_egfr_date=_date_str(400)))  # >12 months
        s = _get_suggestion(results, "R2")
        assert s["status"] == STATUS_DUE


class TestR3Lipids:
    def test_missing_returns_missing(self):
        results = evaluate_rules(_state(last_lipid_date=None))
        s = _get_suggestion(results, "R3")
        assert s["status"] == STATUS_MISSING

    def test_due_over_12_months(self):
        results = evaluate_rules(_state(last_lipid_date=_date_str(400)))
        s = _get_suggestion(results, "R3")
        assert s["status"] == STATUS_DUE

    def test_recent_under_12_months(self):
        results = evaluate_rules(_state(last_lipid_date=_date_str(90)))
        s = _get_suggestion(results, "R3")
        assert s["status"] == STATUS_RECENT


class TestR4EyeAndFoot:
    def test_missing_eye_returns_missing(self):
        results = evaluate_rules(_state(last_eye_date=None))
        s = _get_suggestion(results, "R4", check_type="eye")
        assert s is not None
        assert s["status"] == STATUS_MISSING

    def test_missing_foot_returns_missing(self):
        results = evaluate_rules(_state(last_foot_date=None))
        s = _get_suggestion(results, "R4", check_type="foot")
        assert s is not None
        assert s["status"] == STATUS_MISSING

    def test_old_eye_returns_refer(self):
        results = evaluate_rules(_state(last_eye_date=_date_str(400)))
        s = _get_suggestion(results, "R4", check_type="eye")
        assert s["status"] == STATUS_REFER

    def test_recent_foot_returns_recent(self):
        results = evaluate_rules(_state(last_foot_date=_date_str(100)))
        s = _get_suggestion(results, "R4", check_type="foot")
        assert s["status"] == STATUS_RECENT

    def test_both_eye_and_foot_returned(self):
        results = evaluate_rules(_state())
        eye  = _get_suggestion(results, "R4", check_type="eye")
        foot = _get_suggestion(results, "R4", check_type="foot")
        assert eye is not None
        assert foot is not None


class TestR5CGMTriggered:
    def test_missing_cgm_returns_missing(self):
        results = evaluate_rules(_state(time_in_range_7d=None))
        s = _get_suggestion(results, "R5")
        assert s["status"] == STATUS_MISSING

    def test_good_tir_returns_ok(self):
        results = evaluate_rules(_state(time_in_range_7d=0.80))
        s = _get_suggestion(results, "R5")
        assert s["status"] == STATUS_OK

    def test_low_tir_returns_due(self):
        results = evaluate_rules(_state(time_in_range_7d=0.50))
        s = _get_suggestion(results, "R5")
        assert s["status"] == STATUS_DUE

    def test_many_hypos_returns_due(self):
        results = evaluate_rules(_state(time_in_range_7d=0.75, hypo_events_14d=3))
        s = _get_suggestion(results, "R5")
        assert s["status"] == STATUS_DUE

    def test_threshold_exactly_at_boundary(self):
        # TIR exactly at threshold (0.70) should NOT trigger due
        results = evaluate_rules(_state(time_in_range_7d=0.70))
        s = _get_suggestion(results, "R5")
        assert s["status"] == STATUS_OK


class TestR6ContextOverride:
    def test_high_risk_converts_recent_to_override(self):
        # Give recent dates for all labs
        state = _state(
            last_hba1c_date=_date_str(30),
            last_egfr_date=_date_str(60),
            last_lipid_date=_date_str(90),
            last_eye_date=_date_str(100),
            last_foot_date=_date_str(90),
            time_in_range_7d=0.80,
        )
        results_normal = evaluate_rules(state, active_high_risk=False)
        results_high   = evaluate_rules(state, active_high_risk=True)

        # Without high risk: R1 should be RECENT
        r1_normal = _get_suggestion(results_normal, "R1")
        assert r1_normal["status"] == STATUS_RECENT

        # With high risk: R1 should be OVERRIDE
        r1_high = _get_suggestion(results_high, "R1")
        assert r1_high["status"] == STATUS_OVERRIDE

    def test_no_override_when_no_high_risk(self):
        state = _state(
            last_hba1c_date=_date_str(30),
            time_in_range_7d=0.80,
        )
        results = evaluate_rules(state, active_high_risk=False)
        r1 = _get_suggestion(results, "R1")
        assert r1["status"] != STATUS_OVERRIDE

    def test_override_preserves_original_message(self):
        state = _state(
            last_hba1c_date=_date_str(30),
            time_in_range_7d=0.80,
        )
        results = evaluate_rules(state, active_high_risk=True)
        r1 = _get_suggestion(results, "R1")
        assert "Original:" in r1["message"]


class TestRuleStructure:
    def test_all_suggestions_have_required_fields(self):
        state = _state()
        results = evaluate_rules(state)
        required = {"rule_id", "rule_version", "rule_name", "status", "message",
                    "source_name", "source_url", "review_status"}
        for s in results:
            assert required.issubset(set(s.keys())), f"Missing fields in suggestion: {s}"

    def test_pending_review_status_on_suggestions(self):
        state = _state()
        results = evaluate_rules(state)
        for s in results:
            if s["rule_id"] != "R6":
                assert "pending clinician review" in s["review_status"].lower() or \
                       "always active" in s["review_status"].lower(), \
                    f"Rule {s['rule_id']} missing pending review status"
