import uuid

from pydantic import BaseModel, ConfigDict


class IcuRiskResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    patient_id: uuid.UUID
    probability: float  # 0-1
    risk_level: str  # low / medium / high
    top_factors: list[str]
    model_note: str = (
        "Trained on synthetic seed data for demo purposes. Not validated for clinical use."
    )
