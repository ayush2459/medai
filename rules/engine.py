"""
rules/engine.py
===============
Rule engine for GlucoTwin investigation suggestions.

Evaluates versioned rules from rules_v1.yaml against the per-patient
twin state and returns structured suggestions for the clinician.

IMPORTANT
---------
All outputs are review prompts, NEVER clinical orders.
Every suggestion is labelled with its rule ID, version, source, and
review status ("pending clinician review" unless explicitly overridden).
Missing data returns a clear "missing_data" status, never a guess.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

RULES_PATH = Path(__file__).resolve().parent / "rules_v1.yaml"
EVIDENCE_PATH = Path(__file__).resolve().parent / "evidence_register.csv"

# Status codes
STATUS_DUE     = "DUE"
STATUS_RECENT  = "RECENT"
STATUS_MISSING = "MISSING_DATA"
STATUS_OK      = "OK"
STATUS_REFER   = "REFER"
STATUS_OVERRIDE = "OVERRIDE"


# ── Load rules ────────────────────────────────────────────────────────────────

def _load_rules() -> list[dict]:
    with open(RULES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("rules", [])


def _load_evidence_register() -> dict[str, dict]:
    """Return a dict keyed by rule_id."""
    register: dict[str, dict] = {}
    if not EVIDENCE_PATH.exists():
        return register
    with open(EVIDENCE_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            register[row["rule_id"]] = row
    return register


# ── Date helpers ──────────────────────────────────────────────────────────────

def _days_since(date_str: str | None) -> int | None:
    """Return number of days since `date_str` (ISO format), or None if missing."""
    if not date_str:
        return None
    try:
        d = date.fromisoformat(date_str[:10])
        return (date.today() - d).days
    except (ValueError, TypeError):
        return None


def _months_since(date_str: str | None) -> float | None:
    days = _days_since(date_str)
    return days / 30.5 if days is not None else None


def _suggestion(
    rule: dict,
    status: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> dict:
    return {
        "rule_id":       rule["id"],
        "rule_version":  rule["version"],
        "rule_name":     rule["name"],
        "status":        status,
        "message":       message,
        "source_name":   rule.get("source_name", ""),
        "source_url":    rule.get("source_url", ""),
        "review_status": rule.get("review_status", "pending clinician review"),
        "detail":        detail or {},
    }


# ── Individual rule evaluators ────────────────────────────────────────────────

def _eval_r1(rule: dict, state: dict) -> dict:
    """R1 — HbA1c recency."""
    last_date_str = state.get("last_hba1c_date")
    months = _months_since(last_date_str)
    days   = _days_since(last_date_str)

    interval_stable       = rule.get("interval_months_stable", 6)
    interval_uncontrolled = rule.get("interval_months_uncontrolled", 3)
    interval              = interval_uncontrolled  # conservative default

    if months is None:
        return _suggestion(rule, STATUS_MISSING, rule["output"]["missing"])
    if months < 3:
        msg = rule["output"]["recent"].format(days_ago=days)
        return _suggestion(rule, STATUS_RECENT, msg, {"days_ago": days})
    if months >= interval:
        msg = rule["output"]["due"].format(interval=f"{interval} months")
        return _suggestion(rule, STATUS_DUE, msg, {"months_since": round(months, 1)})
    msg = rule["output"]["recent"].format(days_ago=days)
    return _suggestion(rule, STATUS_RECENT, msg, {"days_ago": days})


def _eval_r2(rule: dict, state: dict) -> dict:
    """R2 — Kidney function."""
    last_date_str = state.get("last_egfr_date")
    months = _months_since(last_date_str)
    days   = _days_since(last_date_str)
    interval = rule.get("interval_months", 12)

    if months is None:
        return _suggestion(rule, STATUS_MISSING, rule["output"]["missing"])
    if months >= interval:
        return _suggestion(rule, STATUS_DUE, rule["output"]["due"], {"months_since": round(months, 1)})
    return _suggestion(rule, STATUS_RECENT, rule["output"]["recent"].format(days_ago=days), {"days_ago": days})


def _eval_r3(rule: dict, state: dict) -> dict:
    """R3 — Lipid profile."""
    last_date_str = state.get("last_lipid_date")
    months = _months_since(last_date_str)
    days   = _days_since(last_date_str)
    interval = rule.get("interval_months", 12)

    if months is None:
        return _suggestion(rule, STATUS_MISSING, rule["output"]["missing"])
    if months >= interval:
        return _suggestion(rule, STATUS_DUE, rule["output"]["due"], {"months_since": round(months, 1)})
    return _suggestion(rule, STATUS_RECENT, rule["output"]["recent"].format(days_ago=days), {"days_ago": days})


def _eval_r4(rule: dict, state: dict) -> list[dict]:
    """R4 — Eye and foot referral reminders (returns two suggestions)."""
    interval = rule.get("interval_months", 12)
    results = []

    for kind in ("eye", "foot"):
        key = f"last_{kind}_date"
        last_date_str = state.get(key)
        months = _months_since(last_date_str)
        days   = _days_since(last_date_str)

        if months is None:
            results.append(_suggestion(rule, STATUS_MISSING, rule["output"][f"{kind}_missing"],
                                       {"check_type": kind}))
        elif months >= interval:
            results.append(_suggestion(rule, STATUS_REFER, rule["output"][f"{kind}_due"],
                                       {"months_since": round(months, 1), "check_type": kind}))
        else:
            msg = rule["output"][f"{kind}_recent"].format(days_ago=days)
            results.append(_suggestion(rule, STATUS_RECENT, msg, {"days_ago": days, "check_type": kind}))

    return results


def _eval_r5(rule: dict, state: dict) -> dict:
    """R5 — CGM-triggered therapy review."""
    tir_threshold   = rule.get("tir_threshold", 0.70)
    hypo_threshold  = rule.get("hypo_count_threshold", 2)

    tir        = state.get("time_in_range_7d")
    hypo_count = state.get("hypo_events_14d", 0)

    if tir is None:
        return _suggestion(rule, STATUS_MISSING, rule["output"]["missing"])

    if tir < tir_threshold:
        msg = rule["output"]["low_tir"].format(tir=tir, threshold=tir_threshold)
        return _suggestion(rule, STATUS_DUE, msg, {"tir": round(tir, 3), "tir_threshold": tir_threshold})

    if (hypo_count or 0) >= hypo_threshold:
        msg = rule["output"]["high_hypo"].format(count=hypo_count)
        return _suggestion(rule, STATUS_DUE, msg, {"hypo_count": hypo_count})

    return _suggestion(rule, STATUS_OK, rule["output"]["ok"])


def _apply_r6_override(
    rule: dict,
    suggestions: list[dict],
    state: dict,
    active_high_risk: bool = False,
) -> list[dict]:
    """
    R6 — Context override: if high-risk alert is active, convert any
    RECENT status to OVERRIDE so the clinician is nudged to re-assess.
    """
    if not active_high_risk:
        return suggestions

    override_note = rule["output"]["override"]
    new_suggestions = []
    for s in suggestions:
        if s["status"] == STATUS_RECENT:
            new_s = dict(s)
            new_s["status"] = STATUS_OVERRIDE
            new_s["message"] = override_note + " [Original: " + s["message"] + "]"
            new_suggestions.append(new_s)
        else:
            new_suggestions.append(s)
    return new_suggestions


# ── Public entry point ────────────────────────────────────────────────────────

def evaluate_rules(
    state: dict,
    active_high_risk: bool = False,
) -> list[dict]:
    """
    Evaluate all active rules for a patient's twin state.

    Parameters
    ----------
    state           : dict from twin/state.py  get_twin_state()
    active_high_risk: True if the current prediction has a 'high' risk band

    Returns
    -------
    List of suggestion dicts (one per sub-rule for R4, one per rule otherwise).
    Each dict contains: rule_id, rule_version, rule_name, status, message,
    source_name, source_url, review_status, detail.
    """
    rules = _load_rules()
    suggestions: list[dict] = []
    r6_rule: dict | None = None

    for rule in rules:
        if not rule.get("active", True):
            continue

        rid = rule["id"]

        if rid == "R1":
            suggestions.append(_eval_r1(rule, state))
        elif rid == "R2":
            suggestions.append(_eval_r2(rule, state))
        elif rid == "R3":
            suggestions.append(_eval_r3(rule, state))
        elif rid == "R4":
            suggestions.extend(_eval_r4(rule, state))
        elif rid == "R5":
            suggestions.append(_eval_r5(rule, state))
        elif rid == "R6":
            r6_rule = rule

    # Apply context override (R6) last
    if r6_rule is not None:
        suggestions = _apply_r6_override(r6_rule, suggestions, state, active_high_risk)

    return suggestions


def get_evidence_register() -> list[dict]:
    """Return the evidence register as a list of dicts."""
    reg = _load_evidence_register()
    return list(reg.values())
