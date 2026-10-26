import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.redis import get_redis_client, TRIAGE_STREAM_KEY
from app.models.encounter import Encounter, EncounterStatus, IntakeRecord, AuditLog
from app.schemas.intake import IntakeCreate, IntakeResponse
from app.services.safety import evaluate_safety

router = APIRouter(prefix="/api/v1/intake", tags=["intake"])


@router.post("", response_model=IntakeResponse, status_code=status.HTTP_201_CREATED)
@router.post(
    "/",
    response_model=IntakeResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def submit_intake(payload: IntakeCreate, db: Session = Depends(get_db)):
    safety_result = evaluate_safety(payload.vitals, payload.symptoms)

    encounter_status = (
        EncounterStatus.VALIDATED
        if safety_result.is_safe
        else EncounterStatus.ESCALATED
    )
    action_required = (
        "TRIAGE_QUEUE"
        if safety_result.is_safe
        else "IMMEDIATE_PHYSICIAN_ATTENTION"
    )

    encounter = Encounter(
        id=str(uuid.uuid4()),
        patient_id=payload.patient_id,
        status=encounter_status,
    )
    db.add(encounter)

    intake_record = IntakeRecord(
        encounter_id=encounter.id,
        age=payload.age,
        weight_kg=payload.weight_kg,
        vitals=payload.vitals.model_dump(),
        symptoms=payload.symptoms,
        free_text=payload.free_text,
        allergies=payload.allergies,
        current_meds=payload.current_meds,
    )
    db.add(intake_record)

    audit_entry = AuditLog(
        encounter_id=encounter.id,
        actor="kiosk_safety_engine",
        action="INTAKE_EVALUATION",
        details={
            "status": encounter_status.value,
            "flags": safety_result.flags,
        },
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(encounter)

    if encounter.status == EncounterStatus.VALIDATED:
        try:
            r = get_redis_client()
            r.xadd(
                TRIAGE_STREAM_KEY,
                {
                    "encounter_id": str(encounter.id),
                    "patient_id": str(encounter.patient_id),
                },
            )
        except Exception as err:
            print(f"redis stream publish error: {err}")

    return IntakeResponse(
        encounter_id=str(encounter.id),
        status=encounter.status.value,
        action_required=action_required,
        safety_flags=safety_result.flags,
    )