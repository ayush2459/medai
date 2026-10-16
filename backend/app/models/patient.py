import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mrn: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)  # medical record number

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[Gender] = mapped_column(
        Enum(Gender, values_callable=lambda enum_cls: [e.value for e in enum_cls], name="gender"),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    blood_type: Mapped[str | None] = mapped_column(String(5), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_admitted: Mapped[bool] = mapped_column(default=False, nullable=False)
    ward: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bed_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    diagnoses: Mapped[list["Diagnosis"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    lab_results: Mapped[list["LabResult"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    notes: Mapped[list["DoctorNote"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    vital_signs: Mapped[list["VitalSign"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    observations: Mapped[list["Observation"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    admission_events: Mapped[list["AdmissionEvent"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    icd_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    diagnosed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    diagnosed_at: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="diagnoses")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    medication_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(String(100), nullable=False)
    prescribed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="prescriptions")


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_abnormal: Mapped[bool] = mapped_column(default=False, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="lab_results")


class DoctorNote(Base):
    __tablename__ = "doctor_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="notes")
