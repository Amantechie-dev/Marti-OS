from typing import List, Optional
from pydantic import BaseModel, Field

class MedicationItem(BaseModel):
    name: str = Field(..., min_length=1)
    dose_mg: float = Field(..., ge=0)
    route: str = Field(..., min_length=1)
    frequency: str = Field(..., min_length=1)
    duration_days: int = Field(..., ge=1)

class PrescriptionData(BaseModel):
    medications: List[MedicationItem]
    instructions: Optional[str] = ""

class ReviewActionRequest(BaseModel):
    doctor_id: str = Field(..., min_length=1)
    decision: str = Field(..., pattern="^(APPROVE|EDIT|REJECT)$")
    final_prescription: Optional[PrescriptionData] = None
    doctor_notes: Optional[str] = ""

class EncounterReviewDetail(BaseModel):
    encounter_id: str
    patient_id: str
    status: str
    vitals: dict
    symptoms: dict
    allergies: List[str]
    current_meds: List[str]
    draft_severity: Optional[str] = None
    draft_note: Optional[str] = None
    draft_prescription: Optional[dict] = None