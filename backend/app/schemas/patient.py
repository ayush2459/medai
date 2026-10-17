import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.patient import Gender


class PatientBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    gender: Gender
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    blood_type: Optional[str] = Field(default=None, max_length=5)
    allergies: Optional[str] = None


class PatientCreate(PatientBase):
    mrn: str = Field(min_length=1, max_length=32)


class PatientUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    blood_type: Optional[str] = Field(default=None, max_length=5)
    allergies: Optional[str] = None
    is_admitted: Optional[bool] = None
    ward: Optional[str] = Field(default=None, max_length=100)
    bed_number: Optional[str] = Field(default=None, max_length=20)


class PatientOut(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mrn: str
    is_admitted: bool
    ward: Optional[str]
    bed_number: Optional[str]
    created_at: datetime
    updated_at: datetime


class DiagnosisCreate(BaseModel):
    icd_code: Optional[str] = Field(default=None, max_length=20)
    description: str = Field(min_length=1, max_length=500)
    notes: Optional[str] = None


class DiagnosisOut(DiagnosisCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    diagnosed_at: date


class PrescriptionCreate(BaseModel):
    medication_name: str = Field(min_length=1, max_length=255)
    dosage: str = Field(min_length=1, max_length=100)
    frequency: str = Field(min_length=1, max_length=100)
    end_date: Optional[date] = None


class PrescriptionOut(PrescriptionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    start_date: date


class LabResultCreate(BaseModel):
    test_name: str = Field(min_length=1, max_length=255)
    value: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=50)
    reference_range: Optional[str] = Field(default=None, max_length=100)
    is_abnormal: bool = False


class LabResultOut(LabResultCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    collected_at: datetime


class NoteCreate(BaseModel):
    content: str = Field(min_length=1)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    author_id: Optional[uuid.UUID]
    content: str
    created_at: datetime


class PatientDetail(PatientOut):
    diagnoses: list[DiagnosisOut] = []
    prescriptions: list[PrescriptionOut] = []
    lab_results: list[LabResultOut] = []
    notes: list[NoteOut] = []


class PaginatedPatients(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PatientOut]
