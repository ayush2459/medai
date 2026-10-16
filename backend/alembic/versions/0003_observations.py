"""add provenance-aware patient observations

Revision ID: 0003_observations
Revises: 0002_clinical_events
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_observations"
down_revision = "0002_clinical_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=True),
        sa.Column("quality_status", sa.String(16), server_default="unverified", nullable=False),
        sa.CheckConstraint(
            "quality_status IN ('unverified', 'valid', 'suspect', 'invalid')",
            name="observation_quality_status",
        ),
    )
    op.create_index("ix_observations_patient_id", "observations", ["patient_id"])
    op.create_index(
        "ix_observations_patient_measured_at",
        "observations",
        ["patient_id", "measured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_observations_patient_measured_at", table_name="observations")
    op.drop_index("ix_observations_patient_id", table_name="observations")
    op.drop_table("observations")
