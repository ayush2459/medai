import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.patient import Diagnosis, DoctorNote, LabResult, Patient, Prescription
from app.models.user import User, UserRole
from app.schemas.patient import (
    DiagnosisCreate,
    DiagnosisOut,
    LabResultCreate,
    LabResultOut,
    NoteCreate,
    NoteOut,
    PaginatedPatients,
    PatientCreate,
    PatientDetail,
    PatientOut,
    PatientUpdate,
    PrescriptionCreate,
    PrescriptionOut,
)

router = APIRouter(prefix="/api/patients", tags=["patients"])

# Roles allowed to create/modify clinical records (not researchers - they're read-only/population level)
CLINICAL_WRITE_ROLES = (UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE)


def _get_patient_or_404(db: Session, patient_id: uuid.UUID) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CLINICAL_WRITE_ROLES)),
):
    existing = db.query(Patient).filter(Patient.mrn == payload.mrn).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MRN already exists")

    patient = Patient(**payload.model_dump(), created_by=current_user.id)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("", response_model=PaginatedPatients)
def list_patients(
    search: str | None = Query(None, description="Search by name or MRN"),
    ward: str | None = None,
    is_admitted: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    query = db.query(Patient)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Patient.first_name.ilike(like), Patient.last_name.ilike(like), Patient.mrn.ilike(like))
        )
    if ward:
        query = query.filter(Patient.ward == ward)
    if is_admitted is not None:
        query = query.filter(Patient.is_admitted == is_admitted)

    total = query.count()
    items = query.order_by(Patient.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedPatients(total=total, page=page, page_size=page_size, items=items)


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return _get_patient_or_404(db, patient_id)


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles(*CLINICAL_WRITE_ROLES)),
):
    patient = _get_patient_or_404(db, patient_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    patient = _get_patient_or_404(db, patient_id)
    db.delete(patient)
    db.commit()


# --- Diagnoses ---


@router.post("/{patient_id}/diagnoses", response_model=DiagnosisOut, status_code=status.HTTP_201_CREATED)
def add_diagnosis(
    patient_id: uuid.UUID,
    payload: DiagnosisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR)),
):
    _get_patient_or_404(db, patient_id)
    diagnosis = Diagnosis(**payload.model_dump(), patient_id=patient_id, diagnosed_by=current_user.id)
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)
    return diagnosis


# --- Prescriptions ---


@router.post("/{patient_id}/prescriptions", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED)
def add_prescription(
    patient_id: uuid.UUID,
    payload: PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR)),
):
    _get_patient_or_404(db, patient_id)
    prescription = Prescription(**payload.model_dump(), patient_id=patient_id, prescribed_by=current_user.id)
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


# --- Lab Results ---


@router.post("/{patient_id}/labs", response_model=LabResultOut, status_code=status.HTTP_201_CREATED)
def add_lab_result(
    patient_id: uuid.UUID,
    payload: LabResultCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles(*CLINICAL_WRITE_ROLES)),
):
    _get_patient_or_404(db, patient_id)
    lab_result = LabResult(**payload.model_dump(), patient_id=patient_id)
    db.add(lab_result)
    db.commit()
    db.refresh(lab_result)
    return lab_result


# --- Doctor Notes ---


@router.post("/{patient_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(
    patient_id: uuid.UUID,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE)),
):
    _get_patient_or_404(db, patient_id)
    note = DoctorNote(**payload.model_dump(), patient_id=patient_id, author_id=current_user.id)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note
