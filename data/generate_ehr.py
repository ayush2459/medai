"""
data/generate_ehr.py
====================
Generates a synthetic cohort of 400 adult Type 2 Diabetes patients following a
Synthea-like CSV schema.  All data is entirely synthetic.  No real patient data
is used or produced.

Output files (written to data/sample/ for the 50-patient sample, and to
data/ for the full cohort):
  patients.parquet        – one row per patient
  medications.parquet     – one row per drug episode
  lab_results.parquet     – one row per lab result (with date)

Usage:
  python data/generate_ehr.py                 # full 400-patient cohort
  python data/generate_ehr.py --sample        # 50-patient sample (3-day window)
  python data/generate_ehr.py --n 400 --out data/

The Synthea CSV column names are documented in the Synthea wiki.  Where we
deviate (e.g. synthetic genetic_risk_score, explicit comorbidity columns) the
README notes the difference.
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ── Reproducibility ──────────────────────────────────────────────────────────
SEED = 42
rng = np.random.default_rng(SEED)

# ── Constants ─────────────────────────────────────────────────────────────────
N_PATIENTS = 400

FIRST_NAMES_M = [
    "Arjun", "Rahul", "Vikram", "Suresh", "Amit", "Ravi", "Anand", "Deepak",
    "Rajesh", "Sanjay", "Karthik", "Nikhil", "Ajay", "Manish", "Pradeep",
    "Ramesh", "Sunil", "Anil", "Vijay", "Prakash",
]
FIRST_NAMES_F = [
    "Priya", "Sunita", "Anjali", "Kavita", "Pooja", "Neha", "Rekha", "Meena",
    "Anita", "Geeta", "Divya", "Lakshmi", "Padma", "Usha", "Shanti",
    "Radha", "Sudha", "Savita", "Nirmala", "Kamala",
]
LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Mehta", "Verma", "Nair",
    "Reddy", "Joshi", "Mishra", "Rao", "Das", "Shah", "Iyer", "Pillai",
    "Choudhury", "Bose", "Chatterjee", "Malhotra",
]

# Drug classes with hypoglycaemia risk flag
DRUG_CLASSES: list[tuple[str, bool]] = [
    ("metformin", False),
    ("sulfonylurea", True),
    ("insulin", True),
    ("dpp4_inhibitor", False),
    ("sglt2_inhibitor", False),
]

# Lab tests with (mean, sd, unit, reference_range_lo, reference_range_hi)
LAB_SPECS: dict[str, tuple[float, float, str, float, float]] = {
    "HbA1c":  (8.0, 1.5, "%",      4.0,  5.6),   # diabetic range: >6.5
    "eGFR":   (70.0, 22.0, "mL/min/1.73m2", 60.0, 120.0),
    "UACR":   (45.0, 60.0, "mg/g", 0.0,  30.0),   # log-normal, scaled below
    "LDL":    (3.2,  1.0, "mmol/L", 0.0,  3.0),
    "HDL":    (1.1,  0.3, "mmol/L", 1.0,  1.6),
    "TG":     (2.0,  1.1, "mmol/L", 0.0,  1.7),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _years_ago(years: float) -> date:
    return date.today() - timedelta(days=int(years * 365.25))


def _random_date_in_last_n_days(n: int) -> date:
    days_ago = int(rng.integers(0, n))
    return date.today() - timedelta(days=days_ago)


def _random_date_in_range(start: date, end: date) -> date:
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=int(rng.integers(0, delta)))


# ── Patient generator ─────────────────────────────────────────────────────────

def generate_patients(n: int = N_PATIENTS) -> pd.DataFrame:
    """Return a DataFrame with one row per patient."""
    rows = []
    for i in range(n):
        pid = f"SYN-{i + 1:04d}"
        sex = "M" if rng.random() < 0.52 else "F"
        age = float(_clamp(rng.normal(57, 12), 30, 80))
        bmi = float(_clamp(rng.normal(27.5, 4.5), 16, 50))
        diabetes_duration_years = float(_clamp(rng.normal(7, 5), 0.5, min(age - 30, 30)))

        # Comorbidities correlated with age + BMI
        hypertension_prob = _clamp(0.1 + 0.008 * age + 0.01 * bmi, 0.05, 0.85)
        hypertension = bool(rng.random() < hypertension_prob)

        # CKD stage 0–3 correlated with age + hypertension
        ckd_logit = -4.0 + 0.04 * age + 0.6 * int(hypertension)
        ckd_prob = 1 / (1 + math.exp(-ckd_logit))
        ckd_stage = 0
        if rng.random() < ckd_prob:
            ckd_stage = int(rng.choice([1, 2, 3], p=[0.5, 0.35, 0.15]))

        family_history = bool(rng.random() < 0.35)

        # Synthetic genetic risk score (0–1): not based on real genomics
        genetic_risk_score = float(_clamp(
            0.2 * int(family_history)
            + 0.1 * (bmi - 18.5) / 30
            + 0.05 * (age - 30) / 50
            + rng.normal(0, 0.15),
            0.0, 1.0,
        ))

        dob = _years_ago(age)

        rows.append({
            "patient_id": pid,
            "age": round(age, 1),
            "sex": sex,
            "date_of_birth": dob.isoformat(),
            "bmi": round(bmi, 1),
            "diabetes_duration_years": round(diabetes_duration_years, 1),
            "hypertension": hypertension,
            "ckd_stage": ckd_stage,
            "family_history": family_history,
            "genetic_risk_score": round(genetic_risk_score, 4),
        })

    return pd.DataFrame(rows)


# ── Medications generator ──────────────────────────────────────────────────────

def generate_medications(patients: pd.DataFrame) -> pd.DataFrame:
    """Return one-to-many medication episodes, correlated with patient profile."""
    rows = []
    today = date.today()

    for _, p in patients.iterrows():
        pid = p["patient_id"]
        duration_y = p["diabetes_duration_years"]
        bmi = p["bmi"]
        # Determine medication regime
        on_metformin = True  # Almost universal first-line in T2D
        # Sulfonylurea if longer duration or higher HbA1c (proxied via bmi/duration)
        on_su = bool(rng.random() < _clamp(0.1 + 0.03 * duration_y + 0.005 * bmi, 0.05, 0.70))
        # Insulin if very long duration or high BMI
        on_insulin = bool(rng.random() < _clamp(-0.1 + 0.04 * duration_y + 0.008 * bmi, 0.0, 0.55))
        # DPP-4 inhibitor (alternative or add-on)
        on_dpp4 = bool(not on_su and not on_insulin and rng.random() < 0.3)
        # SGLT-2 (newer, more prevalent in lower duration or comorbid CV)
        on_sglt2 = bool(rng.random() < 0.2)

        med_flags = [
            ("metformin", False, on_metformin),
            ("sulfonylurea", True, on_su),
            ("insulin", True, on_insulin),
            ("dpp4_inhibitor", False, on_dpp4),
            ("sglt2_inhibitor", False, on_sglt2),
        ]

        diag_date = today - timedelta(days=int(duration_y * 365.25))
        for drug_class, hypo_risk, active in med_flags:
            if not active:
                continue
            # Stagger start dates: metformin starts at diagnosis, others later
            delay_days = 0 if drug_class == "metformin" else int(rng.integers(30, int(duration_y * 365 * 0.8) + 31))
            start_date = diag_date + timedelta(days=delay_days)
            if start_date > today:
                start_date = diag_date
            rows.append({
                "patient_id": pid,
                "drug_class": drug_class,
                "start_date": start_date.isoformat(),
                "end_date": None,   # all current medications
                "hypoglycaemia_risk_flag": hypo_risk,
            })

    return pd.DataFrame(rows)


# ── Lab results generator ──────────────────────────────────────────────────────

def generate_labs(patients: pd.DataFrame) -> pd.DataFrame:
    """Return one-to-many lab results, correlated with patient profile."""
    rows = []
    today = date.today()

    for _, p in patients.iterrows():
        pid = p["patient_id"]
        age = p["age"]
        bmi = p["bmi"]
        duration_y = p["diabetes_duration_years"]
        ckd_stage = p["ckd_stage"]

        # HbA1c: mean increases with duration, variance is moderate
        hba1c_mean = _clamp(6.5 + 0.15 * duration_y + 0.015 * bmi, 6.5, 14.0)
        # Multiple historical HbA1c values
        for months_back in [0, 3, 6, 12, 24]:
            if months_back == 0 or rng.random() < 0.7:
                performed_date = today - timedelta(days=int(months_back * 30.5) + int(rng.integers(0, 15)))
                if performed_date > today:
                    performed_date = today
                value = float(_clamp(rng.normal(hba1c_mean, 0.6), 5.0, 15.0))
                rows.append({
                    "patient_id": pid,
                    "test_code": "HbA1c",
                    "value": round(value, 1),
                    "unit": "%",
                    "performed_date": performed_date.isoformat(),
                    "reference_range_lo": 4.0,
                    "reference_range_hi": 5.6,
                })

        # eGFR: decreases with age + CKD stage
        egfr_mean = _clamp(90 - 0.5 * age - 15 * ckd_stage, 10, 120)
        for months_back in [0, 6, 12]:
            if months_back == 0 or rng.random() < 0.65:
                performed_date = today - timedelta(days=int(months_back * 30.5) + int(rng.integers(0, 15)))
                value = float(_clamp(rng.normal(egfr_mean, 12), 5, 120))
                rows.append({
                    "patient_id": pid,
                    "test_code": "eGFR",
                    "value": round(value, 1),
                    "unit": "mL/min/1.73m2",
                    "performed_date": performed_date.isoformat(),
                    "reference_range_lo": 60.0,
                    "reference_range_hi": 120.0,
                })

        # UACR: log-normal, increases with CKD + duration
        uacr_median = _clamp(20 + 30 * ckd_stage + 2 * duration_y, 5, 3000)
        uacr_val = float(np.exp(rng.normal(math.log(uacr_median), 0.8)))
        performed_date = today - timedelta(days=int(rng.integers(0, 365)))
        rows.append({
            "patient_id": pid,
            "test_code": "UACR",
            "value": round(_clamp(uacr_val, 0.5, 5000), 1),
            "unit": "mg/g",
            "performed_date": performed_date.isoformat(),
            "reference_range_lo": 0.0,
            "reference_range_hi": 30.0,
        })

        # Lipids (LDL, HDL, TG) — annual
        for months_back in [0, 12]:
            if months_back == 0 or rng.random() < 0.6:
                performed_date = today - timedelta(days=int(months_back * 30.5) + int(rng.integers(0, 30)))
                ldl = float(_clamp(rng.normal(3.2 + 0.01 * bmi, 0.9), 0.5, 7.0))
                hdl = float(_clamp(rng.normal(1.1 - 0.005 * bmi, 0.25), 0.4, 2.5))
                tg  = float(_clamp(rng.normal(2.0 + 0.02 * bmi, 0.9), 0.3, 8.0))
                for code, val, lo, hi in [("LDL", ldl, 0.0, 3.0), ("HDL", hdl, 1.0, 1.6), ("TG", tg, 0.0, 1.7)]:
                    rows.append({
                        "patient_id": pid,
                        "test_code": code,
                        "value": round(val, 2),
                        "unit": "mmol/L",
                        "performed_date": performed_date.isoformat(),
                        "reference_range_lo": lo,
                        "reference_range_hi": hi,
                    })

    return pd.DataFrame(rows)


# ── Cohort summary helper ─────────────────────────────────────────────────────

def _hba1c_latest(labs: pd.DataFrame) -> pd.Series:
    """Return latest HbA1c per patient as a Series indexed by patient_id."""
    hba1c = labs[labs["test_code"] == "HbA1c"].copy()
    hba1c["performed_date"] = pd.to_datetime(hba1c["performed_date"])
    return hba1c.sort_values("performed_date").groupby("patient_id")["value"].last()


# ── Main entry point ──────────────────────────────────────────────────────────

def generate(n: int = N_PATIENTS, out_dir: Path = Path("data")) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate and save the full EHR cohort.  Returns (patients, medications, labs)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    patients = generate_patients(n)
    medications = generate_medications(patients)
    labs = generate_labs(patients)

    patients.to_parquet(out_dir / "patients.parquet", index=False)
    medications.to_parquet(out_dir / "medications.parquet", index=False)
    labs.to_parquet(out_dir / "lab_results.parquet", index=False)

    # Attach latest HbA1c to patients for downstream use
    latest_hba1c = _hba1c_latest(labs)
    patients = patients.join(latest_hba1c.rename("hba1c_latest"), on="patient_id")
    # Derive insulin / sulfonylurea flags for the simulator and model
    hypo_risk = medications[medications["hypoglycaemia_risk_flag"]].groupby("patient_id")["drug_class"].apply(list)
    patients["insulin_flag"] = patients["patient_id"].map(lambda pid: "insulin" in hypo_risk.get(pid, []))
    patients["sulfonylurea_flag"] = patients["patient_id"].map(lambda pid: "sulfonylurea" in hypo_risk.get(pid, []))
    patients.to_parquet(out_dir / "patients_with_flags.parquet", index=False)

    print(f"[generate_ehr] Wrote {len(patients)} patients, {len(medications)} med episodes, {len(labs)} lab results → {out_dir}")
    return patients, medications, labs


def generate_sample(out_dir: Path = Path("data/sample")) -> None:
    """Generate a small 50-patient sample for committed demo data."""
    out_dir.mkdir(parents=True, exist_ok=True)
    patients = generate_patients(50)
    medications = generate_medications(patients)
    labs = generate_labs(patients)
    
    # Add medication hypoglycaemia risk flags
    hypo_risk = {}
    for _, med in medications.iterrows():
        pid = med["patient_id"]
        if pid not in hypo_risk:
            hypo_risk[pid] = []
        if med["drug_class"] in ["insulin", "sulfonylurea"]:
            hypo_risk[pid].append(med["drug_class"])
    
    patients["insulin_flag"] = patients["patient_id"].map(lambda pid: "insulin" in hypo_risk.get(pid, []))
    patients["sulfonylurea_flag"] = patients["patient_id"].map(lambda pid: "sulfonylurea" in hypo_risk.get(pid, []))
    
    patients.to_parquet(out_dir / "patients.parquet", index=False)
    medications.to_parquet(out_dir / "medications.parquet", index=False)
    labs.to_parquet(out_dir / "lab_results.parquet", index=False)
    patients.to_parquet(out_dir / "patients_with_flags.parquet", index=False)
    print(f"[generate_ehr] Sample: {len(patients)} patients → {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic T2D EHR cohort")
    parser.add_argument("--sample", action="store_true", help="Generate 50-patient sample")
    parser.add_argument("--n", type=int, default=N_PATIENTS, help="Number of patients")
    parser.add_argument("--out", type=str, default="data", help="Output directory")
    args = parser.parse_args()

    if args.sample:
        generate_sample(Path("data/sample"))
    else:
        generate(args.n, Path(args.out))
