import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.encounter import AuditLog, Encounter, EncounterStatus, IntakeRecord, TriageResult

router = APIRouter(prefix="/api/v1/fulfillment", tags=["fulfillment"])


class DispenseRequest(BaseModel):
    dispensed_by: str
    dispenser_slot: Optional[str] = "SLOT-A1"


class DispenseResponse(BaseModel):
    fulfillment_id: str
    encounter_id: str
    status: str
    dispensed_by: str
    dispenser_slot: Optional[str]


def generate_abdm_fhir_bundle(encounter, intake, triage):
    now_iso = datetime.now(timezone.utc).isoformat()
    patient_ref = f"Patient/{encounter.patient_id}"
    encounter_ref = f"Encounter/{encounter.id}"

    composition = {
        "resourceType": "Composition",
        "id": str(uuid.uuid4()),
        "status": "final",
        "type": {
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": "371530004",
                "display": "Clinical consultation report",
            }],
            "text": "Prescription and Triage Record",
        },
        "subject": {"reference": patient_ref},
        "encounter": {"reference": encounter_ref},
        "date": now_iso,
        "author": [{"display": "Marti Autonomous Clinical Engine"}],
        "title": "Marti Clinical Care Context",
    }

    patient_entry = {
        "resourceType": "Patient",
        "id": str(encounter.patient_id),
    }

    encounter_entry = {
        "resourceType": "Encounter",
        "id": str(encounter.id),
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory triage",
        },
        "subject": {"reference": patient_ref},
    }

    vitals_dict = intake.vitals if intake and intake.vitals else {}
    observation_components = []

    vital_mappings = {
        "hr": ("8867-4", "Heart rate", "/min"),
        "sbp": ("8480-6", "Systolic blood pressure", "mmHg"),
        "dbp": ("8462-4", "Diastolic blood pressure", "mmHg"),
        "spo2": ("59408-5", "Oxygen saturation in Arterial blood", "%"),
        "temp_c": ("8310-5", "Body temperature", "Cel"),
    }

    for key, val in vitals_dict.items():
        if key in vital_mappings and val is not None:
            loinc_code, display_name, unit = vital_mappings[key]
            observation_components.append({
                "code": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": loinc_code,
                        "display": display_name,
                    }]
                },
                "valueQuantity": {
                    "value": float(val),
                    "unit": unit,
                    "system": "http://unitsofmeasure.org",
                    "code": unit,
                },
            })

    observation_entry = {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "vital-signs",
                "display": "Vital Signs",
            }]
        }],
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "85353-1",
                "display": "Vital signs panel",
            }],
            "text": "Vital Signs",
        },
        "subject": {"reference": patient_ref},
        "encounter": {"reference": encounter_ref},
        "component": observation_components,
    }

    med_entries = []
    rx_list = (
        triage.draft_prescription
        if (triage and isinstance(triage.draft_prescription, list))
        else []
    )

    for rx in rx_list:
        med_entries.append({
            "resourceType": "MedicationRequest",
            "id": str(uuid.uuid4()),
            "status": "completed",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "387584000",
                    "display": "Paracetamol",
                }],
                "text": f"{rx.get('drug', 'Paracetamol')} {rx.get('dosage', '500mg')}",
            },
            "subject": {"reference": patient_ref},
            "encounter": {"reference": encounter_ref},
            "dosageInstruction": [{
                "text": f"{rx.get('frequency', 'TDS')} for {rx.get('days', 3)} days",
                "timing": {"code": {"text": rx.get("frequency", "TDS")}},
            }],
        })

    entries = [
        {"resource": composition},
        {"resource": patient_entry},
        {"resource": encounter_entry},
        {"resource": observation_entry},
    ]

    for med in med_entries:
        entries.append({"resource": med})

    return {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "type": "document",
        "timestamp": now_iso,
        "entry": entries,
    }


@router.post("/dispense/{encounter_id}", response_model=DispenseResponse)
@router.post("/dispense/{encounter_id}/", response_model=DispenseResponse, include_in_schema=False)
def dispense_medication(
    encounter_id: str, payload: DispenseRequest, db: Session = Depends(get_db)
):
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"encounter {encounter_id} not found",
        )

    if encounter.status != EncounterStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"encounter status is {encounter.status.value}, must be APPROVED prior to dispensing",
        )

    encounter.status = EncounterStatus.FULFILLED

    audit = AuditLog(
        encounter_id=encounter.id,
        actor=payload.dispensed_by,
        action="PRESCRIPTION_DISPENSED",
        details={
            "slot": payload.dispenser_slot,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(encounter)

    return DispenseResponse(
        fulfillment_id=str(uuid.uuid4()),
        encounter_id=str(encounter.id),
        status="DISPENSED",
        dispensed_by=payload.dispensed_by,
        dispenser_slot=payload.dispenser_slot,
    )


@router.get("/billing/{encounter_id}")
@router.post("/billing/{encounter_id}")
def get_billing_details(encounter_id: str, db: Session = Depends(get_db)):
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"encounter {encounter_id} not found",
        )

    return {
        "encounter_id": str(encounter.id),
        "items": [
            {
                "description": "Tele-triage physician consultation fee",
                "amount_inr": 250.0,
            }
        ],
        "total_amount_inr": 250.0,
        "payment_link": f"https://pay.marti.health/invoice/{encounter.id[:8]}",
        "is_paid": True,
    }


@router.get("/fhir-export/{encounter_id}")
@router.post("/fhir-export/{encounter_id}")
def export_fhir_bundle(encounter_id: str, db: Session = Depends(get_db)):
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"encounter {encounter_id} not found",
        )

    intake = (
        db.query(IntakeRecord)
        .filter(IntakeRecord.encounter_id == encounter.id)
        .first()
    )
    triage = (
        db.query(TriageResult)
        .filter(TriageResult.encounter_id == encounter.id)
        .first()
    )

    return generate_abdm_fhir_bundle(encounter, intake, triage)