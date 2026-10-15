"""add vital_signs and admission_events tables

Revision ID: 0002_clinical_events
Revises: 0001_initial_schema
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_clinical_events"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vital_signs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("heart_rate_bpm", sa.Integer, nullable=True),
        sa.Column("systolic_bp", sa.Integer, nullable=True),
        sa.Column("diastolic_bp", sa.Integer, nullable=True),
        sa.Column("respiratory_rate", sa.Integer, nullable=True),
        sa.Column("temperature_c", sa.Float, nullable=True),
        sa.Column("spo2_percent", sa.Integer, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vital_signs_patient_id", "vital_signs", ["patient_id"])

    op.create_table(
        "admission_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discharged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admitted_to_icu", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ward", sa.String(100), nullable=False),
        sa.Column("admission_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_admission_events_patient_id", "admission_events", ["patient_id"])


def downgrade() -> None:
    op.drop_table("admission_events")
    op.drop_table("vital_signs")
