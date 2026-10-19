from datetime import datetime, timezone
import random
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.ml.features import build_feature_row
from app.ml.inference import ModelNotTrainedError, predict_icu_risk
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.ml import IcuRiskResponse

router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.get("/icu-risk/{patient_id}", response_model=IcuRiskResponse)
def get_icu_risk(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE)
    ),
):
    patient = db.get(Patient, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    feature_row = build_feature_row(
        db, patient, datetime.now(timezone.utc)
    )

    try:
        result = predict_icu_risk(feature_row)
    except ModelNotTrainedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return IcuRiskResponse(patient_id=patient_id, **result)
