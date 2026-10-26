from sqlalchemy.orm import Session
from app.models.encounter import Encounter, EncounterStatus, TriageResult, AuditLog
from app.services.formulary import verify_prescription_safety

def process_triage_for_encounter(encounter_id: str, db: Session) -> dict:
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        return {"error": "encounter not found"}

    if encounter.status != EncounterStatus.VALIDATED:
        return {"error": f"invalid status {encounter.status.value}"}

    intake = encounter.intake
    vitals = intake.vitals if intake else {}
    symptoms = intake.symptoms.get("selected", []) if intake and intake.symptoms else []
    allergies = intake.allergies if intake else []

    temp = vitals.get("temp_c", 37.0)

    # triage rule logic
    medications = []
    if "fever" in symptoms or temp >= 37.5:
        medications.append({
            "name": "paracetamol",
            "dose_mg": 500.0,
            "route": "oral",
            "frequency": "every 6 to 8 hours as needed",
            "duration_days": 3,
        })

    if "runny nose" in symptoms or "sneezing" in symptoms:
        medications.append({
            "name": "cetirizine",
            "dose_mg": 10.0,
            "route": "oral",
            "frequency": "once daily at night",
            "duration_days": 5,
        })

    if not medications:
        medications.append({
            "name": "paracetamol",
            "dose_mg": 500.0,
            "route": "oral",
            "frequency": "as needed for headache or malaise",
            "duration_days": 2,
        })

    # execute post-agent safety check
    safety_violations = verify_prescription_safety(medications, allergies)

    draft_prescription = {
        "medications": medications,
        "instructions": "take medications with water after food",
        "safety_flags": safety_violations,
    }

    triage_result = TriageResult(
        encounter_id=encounter.id,
        severity="urgent" if temp >= 38.5 else "routine",
        draft_note=f"symptoms: {', '.join(symptoms)}. vitals reviewed. temp: {temp} c.",
        draft_prescription=draft_prescription,
        model_version="clinical_rules_v1",
    )
    db.add(triage_result)

    encounter.status = EncounterStatus.PENDING_REVIEW

    audit = AuditLog(
        encounter_id=encounter.id,
        actor="triage_agent",
        action="TRIAGE_COMPLETED",
        details={
            "severity": triage_result.severity,
            "safety_violations": safety_violations,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "encounter_id": encounter.id,
        "status": encounter.status.value,
        "severity": triage_result.severity,
        "medications": medications,
        "safety_violations": safety_violations,
    }