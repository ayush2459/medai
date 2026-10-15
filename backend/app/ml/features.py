"""
Feature engineering for the ICU admission risk model.

One row per AdmissionEvent. Label = admitted_to_icu.
Features are assembled from data that would realistically be available at (or
just before) the time of admission: demographics, the most recent vitals
reading, and a rough comorbidity signal (diagnosis count, abnormal lab count,
prior admission count).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.clinical_events import AdmissionEvent, VitalSign
from app.models.patient import Diagnosis, LabResult, Patient

FEATURE_COLUMNS = [
    "age",
    "gender_male",
    "gender_female",
    "heart_rate_bpm",
    "systolic_bp",
    "diastolic_bp",
    "respiratory_rate",
    "temperature_c",
    "spo2_percent",
    "diagnosis_count",
    "abnormal_lab_count",
    "prior_admission_count",
]

# Population-level fallbacks used when a specific patient has no vitals/labs
# recorded yet (keeps inference robust for brand-new patients).
DEFAULT_VITALS = {
    "heart_rate_bpm": 80,
    "systolic_bp": 120,
    "diastolic_bp": 78,
    "respiratory_rate": 16,
    "temperature_c": 37.0,
    "spo2_percent": 98,
}


def _age_at(dob: date, at_date: date) -> int:
    years = at_date.year - dob.year
    if (at_date.month, at_date.day) < (dob.month, dob.day):
        years -= 1
    return max(years, 0)


def _most_recent_vitals(db: Session, patient_id, before) -> dict:
    row = (
        db.query(VitalSign)
        .filter(VitalSign.patient_id == patient_id, VitalSign.recorded_at <= before)
        .order_by(VitalSign.recorded_at.desc())
        .first()
    )
    if row is None:
        return dict(DEFAULT_VITALS)
    return {
        "heart_rate_bpm": row.heart_rate_bpm if row.heart_rate_bpm is not None else DEFAULT_VITALS["heart_rate_bpm"],
        "systolic_bp": row.systolic_bp if row.systolic_bp is not None else DEFAULT_VITALS["systolic_bp"],
        "diastolic_bp": row.diastolic_bp if row.diastolic_bp is not None else DEFAULT_VITALS["diastolic_bp"],
        "respiratory_rate": row.respiratory_rate
        if row.respiratory_rate is not None
        else DEFAULT_VITALS["respiratory_rate"],
        "temperature_c": row.temperature_c if row.temperature_c is not None else DEFAULT_VITALS["temperature_c"],
        "spo2_percent": row.spo2_percent if row.spo2_percent is not None else DEFAULT_VITALS["spo2_percent"],
    }


def build_feature_row(db: Session, patient: Patient, as_of) -> dict:
    """Build one feature row for `patient` as of a given timestamp (admission time, or 'now' for inference)."""
    age = _age_at(patient.date_of_birth, as_of.date() if hasattr(as_of, "date") else as_of)

    diagnosis_count = db.query(func.count(Diagnosis.id)).filter(Diagnosis.patient_id == patient.id).scalar() or 0
    abnormal_lab_count = (
        db.query(func.count(LabResult.id))
        .filter(LabResult.patient_id == patient.id, LabResult.is_abnormal.is_(True))
        .scalar()
        or 0
    )
    prior_admission_count = (
        db.query(func.count(AdmissionEvent.id))
        .filter(AdmissionEvent.patient_id == patient.id, AdmissionEvent.admitted_at < as_of)
        .scalar()
        or 0
    )
    vitals = _most_recent_vitals(db, patient.id, as_of)

    return {
        "age": age,
        "gender_male": 1 if patient.gender.value == "male" else 0,
        "gender_female": 1 if patient.gender.value == "female" else 0,
        "diagnosis_count": diagnosis_count,
        "abnormal_lab_count": abnormal_lab_count,
        "prior_admission_count": prior_admission_count,
        **vitals,
    }


def build_training_dataframe(db: Session) -> pd.DataFrame:
    events = db.query(AdmissionEvent).order_by(AdmissionEvent.admitted_at).all()
    rows = []
    for event in events:
        patient = db.query(Patient).filter(Patient.id == event.patient_id).first()
        if patient is None:
            continue
        row = build_feature_row(db, patient, event.admitted_at)
        row["label"] = int(event.admitted_to_icu)
        rows.append(row)
    return pd.DataFrame(rows, columns=[*FEATURE_COLUMNS, "label"])
