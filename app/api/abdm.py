from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.abdm import (
    verify_abha_profile,
    validate_abha_number_format,
    validate_abha_address_format,
)

router = APIRouter(prefix="/api/v1/abdm", tags=["abdm-verification"])


class AbhaLookupRequest(BaseModel):
    abha_number: Optional[str] = Field(
        None,
        json_schema_extra={"example": "91-4567-8901-2345"},
    )
    abha_address: Optional[str] = Field(
        None,
        json_schema_extra={"example": "patient777@abdm"},
    )


@router.post("/verify")
def verify_patient_health_id(payload: AbhaLookupRequest):
    if not payload.abha_number and not payload.abha_address:
        raise HTTPException(
            status_code=400,
            detail="must provide either abha_number or abha_address",
        )

    if payload.abha_number and not validate_abha_number_format(payload.abha_number):
        raise HTTPException(
            status_code=400,
            detail="invalid abha number format: expected XX-XXXX-XXXX-XXXX",
        )

    if payload.abha_address and not validate_abha_address_format(payload.abha_address):
        raise HTTPException(
            status_code=400,
            detail="invalid abha address format: expected username@abdm",
        )

    profile = verify_abha_profile(
        abha_number=payload.abha_number,
        abha_address=payload.abha_address,
    )

    if not profile:
        raise HTTPException(status_code=404, detail="abha id not found in abdm registry")

    return {
        "status": "VERIFIED",
        "profile": profile,
    }