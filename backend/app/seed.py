
"""
Seed script: creates a demo admin user, synthetic patients, and
clinical data (diagnoses, lab results, vitals, and admission history)
for the Executive Dashboard and ICU risk model.

IMPORTANT:
- The generated records are synthetic demonstration data.
- This is NOT real epidemiological data or a clinically validated model.
- Existing patients and users are preserved.
- If admission events already exist, seeding is skipped to avoid duplicates.

Usage:
    python -m app.seed
"""

import math
import random
from datetime import date, datetime, timedelta, timezone

from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models.clinical_events import AdmissionEvent, VitalSign
from app.models.patient import Diagnosis, Gender, LabResult, Patient
from app.models.user import User, UserRole


WARDS = [
    "ICU",
    "General A",
    "General B",
    "Cardiology",
    "Pediatrics",
    "Maternity",
]

NON_ICU_WARDS = [ward for ward in WARDS if ward != "ICU"]

DIAGNOSES = [
    ("E11", "Type 2 Diabetes Mellitus"),
    ("I10", "Essential Hypertension"),
    ("J45", "Asthma"),
    ("I21", "Acute Myocardial Infarction"),
    ("N18", "Chronic Kidney Disease"),
    ("J18", "Pneumonia"),
    ("K21", "Gastroesophageal Reflux Disease"),
]

LAB_TESTS = [
    ("Hemoglobin", "g/dL", (12.0, 16.0)),
    ("White Blood Cell Count", "10^3/uL", (4.0, 11.0)),
    ("Creatinine", "mg/dL", (0.6, 1.3)),
    ("Sodium", "mmol/L", (135, 145)),
    ("Potassium", "mmol/L", (3.5, 5.0)),
    ("Glucose", "mg/dL", (70, 140)),
]

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John",
    "Linda", "Michael", "Priya", "Arjun", "Fatima",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Sharma", "Khan",
    "Garcia", "Brown", "Davis", "Patel", "Wilson",
]


def sigmoid(x: float) -> float:
    """Convert a logit value into a probability."""
    return 1 / (1 + math.exp(-x))


def gauss_clamped(
    mean: float,
    sd: float,
    lo: float,
    hi: float,
) -> float:
    """Generate a normally distributed value within given limits."""
    return max(lo, min(hi, random.gauss(mean, sd)))


def seed() -> None:
    """Create demo data without deleting existing patient records."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Ensure a demo admin exists for synthetic records.
        admin_email = "admin@medintel.ai"
        admin = db.query(User).filter(User.email == admin_email).first()

        if admin is None:
            admin = User(
                email=admin_email,
                full_name="Demo Admin",
                hashed_password=hash_password("changeme123"),
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print(f"Created demo admin user: {admin_email}")
        else:
            print(f"Demo admin user already exists: {admin_email}")

        # Check existing data before adding the synthetic cohort.
        existing_count = db.query(Patient).count()
        existing_admission_count = db.query(AdmissionEvent).count()

        if existing_admission_count > 0:
            print(
                f"Found {existing_admission_count} admission events. "
                "Skipping seed to avoid duplicate demo data."
            )
            return

        if existing_count > 0:
            print(
                f"Preserving {existing_count} existing patient(s) "
                "and adding the synthetic demo cohort."
            )

        # Fixed seed makes the generated demo cohort reproducible.
        random.seed(42)

        admission_events_created = 0
        patients_created = 0

        for i in range(150):
            days_ago = random.randint(0, 13)
            created_at = datetime.now(timezone.utc) - timedelta(
                days=days_ago,
                hours=random.randint(0, 23),
            )

            is_admitted = random.random() < 0.35
            dob = date.today() - timedelta(
                days=random.randint(365, 365 * 90)
            )
            age = date.today().year - dob.year

            severity = random.betavariate(2, 5)

            patient = Patient(
                mrn=f"MRN-{1000 + i}",
                first_name=random.choice(FIRST_NAMES),
                last_name=random.choice(LAST_NAMES),
                date_of_birth=dob,
                gender=random.choice(list(Gender)),
                is_admitted=is_admitted,
                ward=random.choice(WARDS) if is_admitted else None,
                created_by=admin.id,
            )

            db.add(patient)
            db.flush()

            patient.created_at = created_at
            patient.updated_at = created_at

            # Generate diagnoses.
            diagnosis_count = 0

            if random.random() < 0.7:
                diagnosis_count = random.randint(1, 2)

                for _ in range(diagnosis_count):
                    icd_code, description = random.choice(DIAGNOSES)

                    db.add(
                        Diagnosis(
                            patient_id=patient.id,
                            icd_code=icd_code,
                            description=description,
                            diagnosed_by=admin.id,
                        )
                    )

            # Generate laboratory results.
            abnormal_lab_count = 0

            for _ in range(random.randint(0, 4)):
                test_name, unit, (lo, hi) = random.choice(LAB_TESTS)

                is_abnormal = random.random() < (
                    0.15 + 0.55 * severity
                )

                if is_abnormal:
                    value = round(
                        random.choice([lo * 0.7, hi * 1.4]),
                        1,
                    )
                    abnormal_lab_count += 1
                else:
                    value = round(random.uniform(lo, hi), 1)

                db.add(
                    LabResult(
                        patient_id=patient.id,
                        test_name=test_name,
                        value=value,
                        unit=unit,
                        reference_range=f"{lo}-{hi}",
                        is_abnormal=is_abnormal,
                    )
                )

            # Generate admission history.
            num_admissions = random.choice([0, 0, 1, 1, 1, 2])

            for admission_index in range(num_admissions):
                days_back = random.randint(1, 179)

                admitted_at = datetime.now(timezone.utc) - timedelta(
                    days=days_back,
                    hours=random.randint(0, 23),
                )

                icu_logit = (
                    -4.2
                    + 0.03 * age
                    + 0.7 * diagnosis_count
                    + 0.9 * abnormal_lab_count
                    + 3.8 * severity
                    + random.gauss(0, 0.6)
                )

                admitted_to_icu = (
                    random.random() < sigmoid(icu_logit)
                )

                # Generate synthetic vitals based on the demo label.
                if admitted_to_icu:
                    heart_rate = round(
                        gauss_clamped(108, 14, 60, 160)
                    )
                    systolic_bp = round(
                        gauss_clamped(94, 16, 60, 160)
                    )
                    diastolic_bp = round(
                        gauss_clamped(58, 10, 35, 100)
                    )
                    respiratory_rate = round(
                        gauss_clamped(27, 4, 12, 40)
                    )
                    temperature_c = round(
                        gauss_clamped(38.4, 0.9, 35.5, 41.0),
                        1,
                    )
                    spo2 = round(
                        gauss_clamped(89, 4, 75, 100)
                    )
                    ward = "ICU"
                    los_hours = gauss_clamped(120, 45, 12, 300)

                else:
                    heart_rate = round(
                        gauss_clamped(78, 11, 50, 130)
                    )
                    systolic_bp = round(
                        gauss_clamped(121, 12, 85, 170)
                    )
                    diastolic_bp = round(
                        gauss_clamped(78, 8, 50, 110)
                    )
                    respiratory_rate = round(
                        gauss_clamped(16, 2.5, 10, 26)
                    )
                    temperature_c = round(
                        gauss_clamped(37.0, 0.5, 35.5, 39.0),
                        1,
                    )
                    spo2 = round(
                        gauss_clamped(97, 1.8, 90, 100)
                    )
                    ward = random.choice(NON_ICU_WARDS)
                    los_hours = gauss_clamped(48, 22, 4, 140)

                vitals_time = admitted_at + timedelta(
                    minutes=random.randint(5, 45)
                )

                db.add(
                    VitalSign(
                        patient_id=patient.id,
                        heart_rate_bpm=heart_rate,
                        systolic_bp=systolic_bp,
                        diastolic_bp=diastolic_bp,
                        respiratory_rate=respiratory_rate,
                        temperature_c=temperature_c,
                        spo2_percent=spo2,
                        recorded_at=vitals_time,
                    )
                )

                is_latest_admission = (
                    admission_index == num_admissions - 1
                )

                discharged_at = (
                    None
                    if is_latest_admission and is_admitted
                    else admitted_at + timedelta(hours=los_hours)
                )

                db.add(
                    AdmissionEvent(
                        patient_id=patient.id,
                        admitted_at=admitted_at,
                        discharged_at=discharged_at,
                        admitted_to_icu=admitted_to_icu,
                        ward=ward,
                        admission_reason=(
                            random.choice(DIAGNOSES)[1]
                            if diagnosis_count
                            else "Routine admission"
                        ),
                    )
                )

                admission_events_created += 1

            patients_created += 1

        # Commit all synthetic cohort records together.
        db.commit()

        print(f"Seeded {patients_created} demo patients.")
        print(
            f"Seeded {admission_events_created} admission events "
            "with vitals for ICU-risk model training."
        )
        print(
            "Existing patient records were preserved. "
            "All generated records are synthetic demo data."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()
