import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ObservationQualityStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    VALID = "valid"
    SUSPECT = "suspect"
    INVALID = "invalid"


class Observation(Base):
    """A provenance-aware, time-stamped observation for a patient."""

    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quality_status: Mapped[ObservationQualityStatus] = mapped_column(
        Enum(
            ObservationQualityStatus,
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
            name="observation_quality_status",
            native_enum=False,
            create_constraint=True,
            length=16,
        ),
        default=ObservationQualityStatus.UNVERIFIED,
        server_default=ObservationQualityStatus.UNVERIFIED.value,
        nullable=False,
    )

    patient: Mapped["Patient"] = relationship(back_populates="observations")  # noqa: F821


class VitalSign(Base):
    """A single vitals reading for a patient (e.g. taken at triage or on rounds)."""

    __tablename__ = "vital_signs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    heart_rate_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    systolic_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diastolic_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    respiratory_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    spo2_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="vital_signs")  # noqa: F821


class AdmissionEvent(Base):
    """
    A real admission/discharge event with an ICU flag - this is the actual outcome
    data needed for ICU-admission-risk model training (and, as a side effect, for
    honest length-of-stay and readmission-rate reporting, which Sprint 2's Executive
    Dashboard could only proxy from patient.created_at).
    """

    __tablename__ = "admission_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admitted_to_icu: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ward: Mapped[str] = mapped_column(String(100), nullable=False)
    admission_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="admission_events")  # noqa: F821
