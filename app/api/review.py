import uuid
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel,ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.encounter import (
    AuditLog,
    Encounter,
    EncounterStatus,
    IntakeRecord,
    TriageResult,
)

router = APIRouter(prefix="/api/v1/review", tags=["review"])


class EncounterReviewDetail(BaseModel):
    encounter_id: str
    patient_id: str
    status: str
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    vitals: Optional[dict[str, Any]] = None
    symptoms: List[str] = Field(default_factory=list)
    free_text: Optional[str] = None
    draft_note: Optional[str] = None
    draft_prescription: List[dict[str, Any]] = Field(default_factory=list)

    
    model_config = ConfigDict(from_attributes=True)


class ReviewDecisionRequest(BaseModel):
    physician_id: str
    decision: str
    clinical_notes: str
    final_prescription: List[dict[str, Any]] = Field(default_factory=list)


class ReviewDecisionResponse(BaseModel):
    encounter_id: str
    status: str
    reviewed_by: str
    next_step: str


@router.get("/pending", response_model=List[EncounterReviewDetail])
def get_pending_reviews(db: Session = Depends(get_db)):
    encounters = (
        db.query(Encounter)
        .filter(Encounter.status == EncounterStatus.PENDING_REVIEW)
        .order_by(Encounter.created_at.asc())
        .all()
    )

    results = []
    for enc in encounters:
        triage = (
            db.query(TriageResult)
            .filter(TriageResult.encounter_id == enc.id)
            .first()
        )
        intake = (
            db.query(IntakeRecord)
            .filter(IntakeRecord.encounter_id == enc.id)
            .first()
        )

        results.append(
            EncounterReviewDetail(
                encounter_id=str(enc.id),
                patient_id=str(enc.patient_id),
                status=enc.status.value,
                age=intake.age if intake else None,
                weight_kg=intake.weight_kg if intake else None,
                vitals=intake.vitals if intake else None,
                symptoms=intake.symptoms if (intake and isinstance(intake.symptoms, list)) else [],
                free_text=intake.free_text if intake else None,
                draft_note=triage.draft_note if triage else None,
                draft_prescription=triage.draft_prescription if (triage and isinstance(triage.draft_prescription, list)) else [],
            )
        )

    return results


@router.post("/{encounter_id}/decision", response_model=ReviewDecisionResponse)
def submit_review_decision(
    encounter_id: str,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
):
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"encounter {encounter_id} not found",
        )

    if encounter.status != EncounterStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"encounter status is {encounter.status.value}, expected PENDING_REVIEW",
        )

    if payload.decision.upper() == "APPROVE":
        encounter.status = EncounterStatus.APPROVED
        next_step = "READY_FOR_DISPENSING"
    else:
        encounter.status = EncounterStatus.REJECTED
        next_step = "CONSULTATION_TERMINATED"

    triage = db.query(TriageResult).filter(TriageResult.encounter_id == encounter.id).first()
    if triage and payload.final_prescription:
        triage.draft_prescription = payload.final_prescription

    audit = AuditLog(
        encounter_id=encounter.id,
        actor=payload.physician_id,
        action=f"PHYSICIAN_REVIEW_{payload.decision.upper()}",
        details={
            "notes": payload.clinical_notes,
            "prescriptions": payload.final_prescription,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(encounter)

    return ReviewDecisionResponse(
        encounter_id=str(encounter.id),
        status=encounter.status.value,
        reviewed_by=payload.physician_id,
        next_step=next_step,
    )