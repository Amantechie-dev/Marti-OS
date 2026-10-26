import secrets
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.encounter import Encounter, EncounterStatus, AuditLog

CONSULTATION_FEE_INR = 250.0

MEDICATION_PRICES_INR = {
    "paracetamol": 30.0,
    "cetirizine": 45.0,
    "ibuprofen": 40.0,
    "saline nasal spray": 95.0,
}

def generate_billing_for_encounter(encounter: Encounter, db: Session) -> Dict[str, Any]:
    items = [
        {"description": "Tele-triage physician consultation fee", "amount_inr": CONSULTATION_FEE_INR}
    ]

    total = CONSULTATION_FEE_INR

    # read approved prescription from approval record
    rx = encounter.approval.final_prescription if encounter.approval else None
    if rx and "medications" in rx:
        for med in rx["medications"]:
            name = med.get("name", "").lower()
            price = MEDICATION_PRICES_INR.get(name, 50.0)
            items.append({"description": f"Medication: {name.capitalize()}", "amount_inr": price})
            total += price

    # log billing audit
    audit = AuditLog(
        encounter_id=encounter.id,
        actor="billing_engine",
        action="INVOICE_GENERATED",
        details={"total_amount_inr": total, "items": items},
    )
    db.add(audit)
    db.commit()

    return {
        "encounter_id": encounter.id,
        "items": items,
        "total_amount_inr": total,
        "payment_link": f"https://pay.marti.health/invoice/{encounter.id[:8]}",
        "is_paid": True,
    }

def generate_cabinet_dispense(encounter: Encounter, db: Session) -> Dict[str, Any]:
    rx = encounter.approval.final_prescription if encounter.approval else {}
    meds = rx.get("medications", []) if rx else []

    # create a secure 6-digit one-time pickup pin
    pickup_code = f"{secrets.randbelow(900000) + 100000}"
    slot_id = (abs(hash(encounter.id)) % 24) + 1

    encounter.status = EncounterStatus.DISPENSED

    audit = AuditLog(
        encounter_id=encounter.id,
        actor="automated_cabinet",
        action="MEDICINE_DISPENSED",
        details={"slot": slot_id, "pickup_code": pickup_code},
    )
    db.add(audit)
    db.commit()

    return {
        "encounter_id": encounter.id,
        "cabinet_slot": slot_id,
        "medications": meds,
        "pickup_code": pickup_code,
        "expires_in_minutes": 15,
        "is_dispensed": True,
    }

def export_fhir_bundle(encounter: Encounter) -> Dict[str, Any]:
    intake = encounter.intake
    approval = encounter.approval

    return {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": encounter.patient_id,
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": encounter.id,
                    "status": "finished",
                    "class": {"code": "AMB", "display": "ambulatory triage"},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"text": "Vital Signs"},
                    "valueQuantity": intake.vitals if intake else {},
                }
            },
            {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "status": "completed",
                    "intent": "order",
                    "medicationCodeableConcept": approval.final_prescription if approval else {},
                }
            },
        ],
    }