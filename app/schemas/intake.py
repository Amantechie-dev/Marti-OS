import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class VitalsInput(BaseModel):
    hr: float
    sbp: float
    dbp: float
    spo2: float
    temp_c: float


class SafetyEvaluation(BaseModel):
    is_safe: bool
    flags: List[str]


class IntakeCreate(BaseModel):
    patient_id: str
    age: int = Field(..., ge=0, le=125)
    weight_kg: float = Field(..., gt=0.0, le=300.0)
    vitals: VitalsInput
    symptoms: List[str]
    free_text: Optional[str] = None
    allergies: List[str] = Field(default_factory=list)
    current_meds: List[str] = Field(default_factory=list)
    abha_number: Optional[str] = Field(
        None,
        json_schema_extra={"example": "91-4567-8901-2345"},
    )
    abha_address: Optional[str] = Field(
        None,
        json_schema_extra={"example": "patient777@abdm"},
    )

    @field_validator("abha_number")
    @classmethod
    def check_abha_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not re.match(r"^\d{2}-\d{4}-\d{4}-\d{4}$", clean):
                raise ValueError("abha number must follow XX-XXXX-XXXX-XXXX format")
            return clean
        return v

    @field_validator("abha_address")
    @classmethod
    def check_abha_address(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().lower()
            if not re.match(r"^[a-zA-Z0-9._]{3,32}@[a-zA-Z0-9]{3,16}$", clean):
                raise ValueError("abha address must follow username@abdm format")
            return clean
        return v


IntakeRequest = IntakeCreate


class IntakeResponse(BaseModel):
    encounter_id: str
    status: str
    action_required: str
    safety_flags: List[str]