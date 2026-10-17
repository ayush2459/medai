"""
data/simulate_wearable.py
=========================
Physiologically inspired simulator for wearable time series.

For each patient it produces 21 days of 5-minute readings:
  - CGM glucose (mg/dL), with NaN sensor dropouts
  - heart_rate (bpm)
  - hrv_rmssd (ms)
  - steps (counts per 5-min interval)
  - sleep_stage (0=awake, 1=light, 2=deep, 3=REM)

Key mechanisms
--------------
  * Baseline mean glucose derived from HbA1c using:
      eAG (mg/dL) = 28.7 * HbA1c(%) - 46.7
  * 3 meals / day with randomised carbohydrate load; post-meal gamma rise
    scaled by insulin sensitivity (function of BMI, age, drugs)
  * Dawn effect: glucose rises ~15–30 mg/dL in the 2-3 h before waking
  * Exercise lowers glucose (15–40 mg/dL drop during activity)
  * Poor previous-night sleep raises next-day baseline by 5–15 mg/dL
  * Sulfonylurea / insulin adds hypoglycaemia events
  * AR(1) sensor noise, random dropout bursts, clip to 40–400 mg/dL
  * Missing = NaN (never 0)
  * HRV falls with poor sleep and stress days
  * Steps follow a daily routine with random activity bouts

Output
------
  wearable.parquet – one row per 5-min interval per patient
    columns: patient_id, timestamp, glucose_mg_dl, heart_rate,
             hrv_rmssd, steps, sleep_stage, sensor_quality_flag

Usage:
  python data/simulate_wearable.py                   # full 400 patients
  python data/simulate_wearable.py --sample          # 50 patients, 3 days
  python data/simulate_wearable.py --pid SYN-0001    # single patient (debug)
"""
from __future__ import annotations

import argparse
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ── Reproducibility ──────────────────────────────────────────────────────────
SEED = 42

# ── Simulation constants ──────────────────────────────────────────────────────
DAYS = 21
INTERVAL_MIN = 5          # CGM sampling interval
READINGS_PER_DAY = 24 * 60 // INTERVAL_MIN  # = 288
TOTAL_READINGS = DAYS * READINGS_PER_DAY

GLUCOSE_CLIP_LO = 40.0
GLUCOSE_CLIP_HI = 400.0

HYPER_THRESHOLD = 180.0
HYPO_THRESHOLD  = 70.0

DROPOUT_PROB       = 0.015   # per-reading base dropout probability
DROPOUT_BURST_PROB = 0.60    # probability that next reading is also dropout if current is
NOISE_AR_COEF      = 0.55    # AR(1) autocorrelation for sensor noise
NOISE_SD           = 3.5     # residual noise SD (mg/dL)


# ── Glucose utility functions ─────────────────────────────────────────────────

def hba1c_to_eag(hba1c: float) -> float:
    """Estimated Average Glucose (mg/dL) from HbA1c (%).  ADA formula."""
    return 28.7 * hba1c - 46.7


def _insulin_sensitivity(age: float, bmi: float, insulin: bool, su: bool) -> float:
    """
    Return an insulin sensitivity factor S in (0,1].
    Higher = more sensitive; lower = more resistant.
    """
    # Base: decreases with age and BMI
    s = _clamp(1.2 - 0.005 * age - 0.008 * bmi, 0.1, 1.0)
    # Insulin/SU users have better glycaemic control but risk of hypo
    if insulin:
        s *= 1.15
    elif su:
        s *= 1.08
    return _clamp(s, 0.10, 1.20)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ── Sleep and activity simulators ────────────────────────────────────────────

def _generate_sleep(rng: np.random.Generator, day: int) -> np.ndarray:
    """
    Return a (READINGS_PER_DAY,) array of sleep_stage integers.
    0=awake, 1=light, 2=deep, 3=REM.
    Sleep typically 22:00–06:30 (10pm–6:30am).
    """
    stages = np.zeros(READINGS_PER_DAY, dtype=np.int8)
    # sleep start: index ~22*12 = 264; end: ~6.5*12 = 78 (next day wraps)
    sleep_start_idx = int(22 * 12)
    sleep_end_idx   = int(6.5 * 12)

    # Vary sleep quality day to day
    quality = rng.choice(["good", "fair", "poor"], p=[0.55, 0.30, 0.15])
    # Decide sleep duration
    if quality == "good":
        dur_h = rng.uniform(7.0, 8.5)
    elif quality == "fair":
        dur_h = rng.uniform(5.5, 7.0)
    else:
        dur_h = rng.uniform(3.5, 5.5)

    dur_readings = int(dur_h * 12)
    # Sleep starts near planned time with ±30 min jitter
    actual_start = sleep_start_idx + int(rng.integers(-6, 7))
    actual_start = actual_start % READINGS_PER_DAY

    # Assign sleep stages: light → deep → REM cycles every ~90 min
    for offset in range(dur_readings):
        idx = (actual_start + offset) % READINGS_PER_DAY
        cycle_pos = (offset * INTERVAL_MIN) % 90  # minutes into 90-min cycle
        if cycle_pos < 20:
            stages[idx] = 1   # light
        elif cycle_pos < 45:
            stages[idx] = 2   # deep
        elif cycle_pos < 75:
            stages[idx] = 3   # REM
        else:
            stages[idx] = 1   # light

    return stages, quality, dur_h


def _generate_steps(rng: np.random.Generator, sleep: np.ndarray) -> np.ndarray:
    """Return steps per 5-min interval; 0 during sleep and night."""
    steps = np.zeros(READINGS_PER_DAY, dtype=np.float32)
    # Activity bouts during waking hours
    awake_idxs = np.where(sleep == 0)[0]
    for i in awake_idxs:
        hour = (i * INTERVAL_MIN) / 60
        if 7 <= hour <= 9:          # morning commute / activity
            steps[i] = rng.exponential(20)
        elif 12 <= hour <= 14:      # post-lunch walk
            steps[i] = rng.exponential(12)
        elif 17 <= hour <= 19:      # evening activity
            steps[i] = rng.exponential(18)
        else:
            steps[i] = rng.exponential(4)
    # Random exercise bout: 30–60 min walk, probability ~35% per day
    if rng.random() < 0.35:
        start_h = rng.uniform(7, 20)
        dur_h = rng.uniform(0.5, 1.5)
        start_idx = int(start_h * 12)
        end_idx = min(READINGS_PER_DAY, start_idx + int(dur_h * 12))
        steps[start_idx:end_idx] += rng.uniform(80, 160, size=end_idx - start_idx)
    return np.round(steps).astype(np.float32)


# ── Heart rate and HRV ────────────────────────────────────────────────────────

def _generate_hr_hrv(
    rng: np.random.Generator,
    sleep: np.ndarray,
    steps: np.ndarray,
    sleep_quality: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Return heart_rate and hrv_rmssd arrays."""
    hr  = np.zeros(READINGS_PER_DAY, dtype=np.float32)
    hrv = np.zeros(READINGS_PER_DAY, dtype=np.float32)
    base_hr = rng.uniform(65, 85)

    # HRV quality modifier
    hrv_quality_mult = {"good": 1.0, "fair": 0.80, "poor": 0.60}[sleep_quality]

    for i in range(READINGS_PER_DAY):
        s = int(sleep[i])
        act = float(steps[i])
        if s > 0:   # sleeping
            r = rng.uniform(50, 62)
            h = rng.normal(45 * hrv_quality_mult, 8)
        else:       # awake
            r = base_hr + 0.03 * act + rng.normal(0, 4)
            h = rng.normal(35 * hrv_quality_mult, 7) - 0.04 * act
        hr[i]  = float(_clamp(r, 35, 180))
        hrv[i] = float(_clamp(h,  5, 120))

    return hr, hrv


# ── Glucose simulator ─────────────────────────────────────────────────────────

def _gamma_rise(t: float, peak_t: float, peak_val: float) -> float:
    """
    Gamma-shaped post-meal glucose excursion.
    t          – minutes since meal
    peak_t     – time to peak (min), typically 45–75
    peak_val   – peak height above baseline (mg/dL)
    """
    if t < 0 or t > 4 * peak_t:
        return 0.0
    k = (peak_t / 20) ** 2
    theta = peak_t / k
    # Gamma pdf (unnormalised)
    scale = peak_val * math.exp(1) / (k * theta ** (k - 1) * math.exp(-1) + 1e-9)
    try:
        val = scale * (t / theta) ** (k - 1) * math.exp(-t / theta)
    except (OverflowError, ZeroDivisionError):
        val = 0.0
    return float(_clamp(val, 0, peak_val * 1.5))


def simulate_glucose(
    rng: np.random.Generator,
    hba1c: float,
    bmi: float,
    age: float,
    insulin_flag: bool,
    sulfonylurea_flag: bool,
    sleep_quality_days: list[str],
    steps_all: np.ndarray,   # shape (days, READINGS_PER_DAY)
    sleep_all: np.ndarray,   # shape (days, READINGS_PER_DAY)
) -> np.ndarray:
    """
    Return a (days * READINGS_PER_DAY,) glucose array with NaN dropouts.
    """
    eag = hba1c_to_eag(hba1c)
    sensitivity = _insulin_sensitivity(age, bmi, insulin_flag, sulfonylurea_flag)

    days = len(sleep_all)  # Infer actual number of days from input array
    glucose = np.full(days * READINGS_PER_DAY, np.nan)
    # Starting glucose near eAG
    g = float(_clamp(eag + rng.normal(0, 15), GLUCOSE_CLIP_LO, GLUCOSE_CLIP_HI))

    noise_prev = 0.0
    in_dropout = False

    for day in range(days):
        prev_night_quality = sleep_quality_days[day - 1] if day > 0 else "good"
        sleep_penalty = {"good": 0.0, "fair": 7.0, "poor": 14.0}[prev_night_quality]
        daily_baseline = eag + sleep_penalty + rng.normal(0, 5)

        # 3 meals: breakfast ~7h, lunch ~13h, dinner ~19h (±30 min)
        meal_times_h = [
            rng.uniform(6.5, 8.0),
            rng.uniform(12.5, 14.0),
            rng.uniform(18.5, 20.0),
        ]
        # Carb load (grams) determines peak rise
        carb_loads = rng.uniform(25, 90, 3)

        # Dawn effect: starts 3 h before wake (~4 AM), peaks at wake
        dawn_start_idx = int((4 * 60) / INTERVAL_MIN)
        dawn_peak_idx  = int((7 * 60) / INTERVAL_MIN)

        for tick in range(READINGS_PER_DAY):
            global_idx = day * READINGS_PER_DAY + tick
            t_min = tick * INTERVAL_MIN  # minutes from midnight

            # Mean-revert toward daily baseline (slow drift)
            g += 0.04 * (daily_baseline - g)

            # Dawn effect
            if dawn_start_idx <= tick <= dawn_peak_idx:
                frac = (tick - dawn_start_idx) / max(1, dawn_peak_idx - dawn_start_idx)
                dawn_rise = rng.normal(20, 5) * math.sin(math.pi * frac)
                g += dawn_rise * 0.08   # incremental per step

            # Post-meal rises
            for meal_h, carbs in zip(meal_times_h, carb_loads):
                t_since_meal = t_min - meal_h * 60
                peak_t = rng.uniform(45, 75)
                # peak_val is scaled by carbs and inversely by sensitivity
                peak_val = (carbs / 50) * (40 + 30 * (1 - sensitivity))
                rise = _gamma_rise(t_since_meal, peak_t, peak_val)
                g += rise * 0.07 * INTERVAL_MIN   # spread the rise over the interval

            # Exercise lowers glucose
            step_val = float(steps_all[day, tick])
            if step_val > 20:
                exercise_drop = 0.015 * step_val * sensitivity
                g -= exercise_drop

            # Hypoglycaemia events for SU / insulin users
            hypo_event = False
            if insulin_flag or sulfonylurea_flag:
                # Hypo risk on empty stomach or after exercise
                hypo_risk_score = (
                    0.005 * max(0, 100 - g)   # more likely when already low
                    + 0.002 * step_val          # exercise increases hypo risk
                    + (0.003 if insulin_flag else 0.0015)
                )
                if rng.random() < hypo_risk_score * INTERVAL_MIN / 60:
                    # Rapid drop to hypo territory
                    hypo_target = rng.uniform(45, 68)
                    g = hypo_target + rng.normal(0, 3)
                    hypo_event = True

            # AR(1) noise
            noise = NOISE_AR_COEF * noise_prev + rng.normal(0, NOISE_SD)
            noise_prev = noise
            g_noisy = g + noise

            # Clip
            g_noisy = float(_clamp(g_noisy, GLUCOSE_CLIP_LO, GLUCOSE_CLIP_HI))
            g = float(_clamp(g, GLUCOSE_CLIP_LO, GLUCOSE_CLIP_HI))  # keep underlying trace in bounds

            # Sensor dropout
            if in_dropout:
                dropout = rng.random() < DROPOUT_BURST_PROB
            else:
                dropout = rng.random() < DROPOUT_PROB
            in_dropout = dropout

            glucose[global_idx] = np.nan if dropout else g_noisy

    return glucose


# ── Main simulation per patient ────────────────────────────────────────────────

def simulate_patient(
    patient: dict,
    rng: np.random.Generator,
    days: int = DAYS,
) -> pd.DataFrame:
    """Simulate `days` days of wearable data for one patient."""
    hba1c = float(patient.get("hba1c_latest", 8.0) or 8.0)
    bmi   = float(patient["bmi"])
    age   = float(patient["age"])
    insulin = bool(patient.get("insulin_flag", False))
    su      = bool(patient.get("sulfonylurea_flag", False))
    pid     = str(patient["patient_id"])

    # Simulate day-by-day
    sleep_all   = np.zeros((days, READINGS_PER_DAY), dtype=np.int8)
    steps_all   = np.zeros((days, READINGS_PER_DAY), dtype=np.float32)
    hr_all      = np.zeros((days, READINGS_PER_DAY), dtype=np.float32)
    hrv_all     = np.zeros((days, READINGS_PER_DAY), dtype=np.float32)
    sleep_qualities: list[str] = []

    for d in range(days):
        sleep_all[d], quality, _ = _generate_sleep(rng, d)
        sleep_qualities.append(quality)
        steps_all[d] = _generate_steps(rng, sleep_all[d])
        hr_all[d], hrv_all[d] = _generate_hr_hrv(rng, sleep_all[d], steps_all[d], quality)

    glucose = simulate_glucose(
        rng, hba1c, bmi, age, insulin, su,
        sleep_qualities, steps_all, sleep_all,
    )

    # Build timestamp index starting 21 days ago from today midnight
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    timestamps = [start + timedelta(minutes=i * INTERVAL_MIN) for i in range(days * READINGS_PER_DAY)]

    df = pd.DataFrame({
        "patient_id":        pid,
        "timestamp":         timestamps,
        "glucose_mg_dl":     glucose,                    # NaN = missing (dropout)
        "heart_rate":        hr_all.flatten().astype(np.float32),
        "hrv_rmssd":         hrv_all.flatten().astype(np.float32),
        "steps":             steps_all.flatten().astype(np.float32),
        "sleep_stage":       sleep_all.flatten().astype(np.int8),
        "sensor_quality_flag": (~np.isnan(glucose)).astype(np.int8),  # 1=valid, 0=dropout
    })
    return df


# ── Cohort runner ─────────────────────────────────────────────────────────────

def simulate_cohort(
    patients_path: Path,
    out_dir: Path,
    days: int = DAYS,
    n_patients: int | None = None,
) -> None:
    """Simulate wearable data for the full cohort and write wearable.parquet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    patients_df = pd.read_parquet(patients_path)
    if n_patients:
        patients_df = patients_df.head(n_patients)

    rng_global = np.random.default_rng(SEED)
    frames: list[pd.DataFrame] = []
    hyper_counts = []
    hypo_counts  = []

    for _, row in patients_df.iterrows():
        # Per-patient RNG for reproducibility: seed from global rng
        patient_seed = int(rng_global.integers(0, 2**31))
        patient_rng  = np.random.default_rng(patient_seed)
        df = simulate_patient(row.to_dict(), patient_rng, days=days)
        frames.append(df)

        # Log actual event rates
        valid = df["glucose_mg_dl"].dropna()
        n_windows = max(1, len(valid) - 24)  # approx 2-hour windows
        hyper_w = sum(valid.iloc[i:i+24].max() > HYPER_THRESHOLD for i in range(n_windows))
        hypo_w  = sum(valid.iloc[i:i+24].min() < HYPO_THRESHOLD  for i in range(n_windows))
        hyper_counts.append(hyper_w / n_windows)
        hypo_counts.append(hypo_w / n_windows)

    wearable = pd.concat(frames, ignore_index=True)
    wearable.to_parquet(out_dir / "wearable.parquet", index=False)

    print(f"[simulate_wearable] {len(patients_df)} patients × {days} days → {out_dir}/wearable.parquet")
    print(f"  Avg hyper-event window rate: {sum(hyper_counts)/len(hyper_counts):.1%}")
    print(f"  Avg hypo-event window rate:  {sum(hypo_counts)/len(hypo_counts):.1%}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate wearable time series for T2D cohort")
    parser.add_argument("--sample",  action="store_true", help="Generate 50-patient × 3-day sample")
    parser.add_argument("--pid",     type=str, default=None, help="Simulate a single patient ID")
    parser.add_argument("--days",    type=int, default=DAYS, help="Simulation duration (days)")
    parser.add_argument("--n",       type=int, default=None, help="Number of patients to simulate")
    parser.add_argument("--out",     type=str, default="data", help="Output directory")
    args = parser.parse_args()

    pat_path = Path(args.out) / "patients_with_flags.parquet"
    if args.sample:
        simulate_cohort(
            Path("data/sample/patients.parquet"),
            Path("data/sample"),
            days=3,
            n_patients=50,
        )
    else:
        simulate_cohort(
            pat_path,
            Path(args.out),
            days=args.days,
            n_patients=args.n,
        )
