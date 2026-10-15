import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.patient import Gender


class PatientBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    gender: Gender
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    blood_type: str | None = Field(default=None, max_length=5)
    allergies: str | None = None


class PatientCreate(PatientBase):
    mrn: str = Field(min_length=1, max_length=32)


class PatientUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    blood_type: str | None = Field(default=None, max_length=5)
    allergies: str | None = None
    is_admitted: bool | None = None
    ward: str | None = Field(default=None, max_length=100)
    bed_number: str | None = Field(default=None, max_length=20)


class PatientOut(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mrn: str
    is_admitted: bool
    ward: str | None
    bed_number: str | None
    created_at: datetime
    updated_at: datetime


class DiagnosisCreate(BaseModel):
    icd_code: str | None = Field(default=None, max_length=20)
    description: str = Field(min_length=1, max_length=500)
    notes: str | None = None


class DiagnosisOut(DiagnosisCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    diagnosed_at: date


class PrescriptionCreate(BaseModel):
    medication_name: str = Field(min_length=1, max_length=255)
    dosage: str = Field(min_length=1, max_length=100)
    frequency: str = Field(min_length=1, max_length=100)
    end_date: date | None = None


class PrescriptionOut(PrescriptionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    start_date: date


class LabResultCreate(BaseModel):
    test_name: str = Field(min_length=1, max_length=255)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=50)
    reference_range: str | None = Field(default=None, max_length=100)
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
    author_id: uuid.UUID | None
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
