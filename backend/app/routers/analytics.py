from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.patient import Diagnosis, Patient
from app.models.user import User
from app.schemas.analytics import DailyCount, DiagnosisCount, ExecutiveSummary, WardCount

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/executive", response_model=ExecutiveSummary)
def get_executive_summary(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    total_patients = db.query(func.count(Patient.id)).scalar() or 0
    currently_admitted = db.query(func.count(Patient.id)).filter(Patient.is_admitted.is_(True)).scalar() or 0

    total_bed_capacity = settings.TOTAL_BED_CAPACITY
    occupancy_rate = round(currently_admitted / total_bed_capacity, 4) if total_bed_capacity > 0 else 0.0

    seven_days_ago = date.today() - timedelta(days=7)
    new_patients_last_7_days = (
        db.query(func.count(Patient.id)).filter(func.date(Patient.created_at) >= seven_days_ago).scalar() or 0
    )

    # Admissions trend: patient records created per day, last 14 days (proxy for admissions
    # since Sprint 1 doesn't yet track dedicated admission/discharge events)
    fourteen_days_ago = date.today() - timedelta(days=13)
    trend_rows = (
        db.query(func.date(Patient.created_at).label("day"), func.count(Patient.id).label("count"))
        .filter(func.date(Patient.created_at) >= fourteen_days_ago)
        .group_by(func.date(Patient.created_at))
        .order_by(func.date(Patient.created_at))
        .all()
    )
    trend_by_day = {row.day: row.count for row in trend_rows}
    admissions_trend = [
        DailyCount(day=fourteen_days_ago + timedelta(days=i), count=trend_by_day.get(fourteen_days_ago + timedelta(days=i), 0))
        for i in range(14)
    ]

    ward_rows = (
        db.query(Patient.ward, func.count(Patient.id).label("count"))
        .filter(Patient.is_admitted.is_(True), Patient.ward.isnot(None))
        .group_by(Patient.ward)
        .order_by(func.count(Patient.id).desc())
        .all()
    )
    ward_distribution = [WardCount(ward=row.ward, count=row.count) for row in ward_rows]

    diagnosis_rows = (
        db.query(Diagnosis.description, func.count(Diagnosis.id).label("count"))
        .group_by(Diagnosis.description)
        .order_by(func.count(Diagnosis.id).desc())
        .limit(5)
        .all()
    )
    top_diagnoses = [DiagnosisCount(description=row.description, count=row.count) for row in diagnosis_rows]

    return ExecutiveSummary(
        total_patients=total_patients,
        currently_admitted=currently_admitted,
        total_bed_capacity=total_bed_capacity,
        occupancy_rate=occupancy_rate,
        new_patients_last_7_days=new_patients_last_7_days,
        admissions_trend=admissions_trend,
        ward_distribution=ward_distribution,
        top_diagnoses=top_diagnoses,
    )
