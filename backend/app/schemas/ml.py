import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class IcuRiskResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), extra="allow")

    patient_id: uuid.UUID
    probability: float = 0.45
    risk_level: str = "medium"
    top_factors: list[str] = [
        "Age above 65",
        "Recent hospital admission",
        "Elevated glucose levels",
    ]
    risk_score: Optional[float] = 0.45
    contributing_factors: Optional[Any] = None
    model_note: str = (
        "Trained on synthetic seed data for demo purposes. Not validated for clinical use."
    )