from datetime import date

from pydantic import BaseModel


class DailyCount(BaseModel):
    day: date
    count: int


class WardCount(BaseModel):
    ward: str
    count: int


class DiagnosisCount(BaseModel):
    description: str
    count: int


class ExecutiveSummary(BaseModel):
    total_patients: int
    currently_admitted: int
    total_bed_capacity: int
    occupancy_rate: float  # 0-1
    new_patients_last_7_days: int
    admissions_trend: list[DailyCount]  # last 14 days, by patient record creation date
    ward_distribution: list[WardCount]
    top_diagnoses: list[DiagnosisCount]
