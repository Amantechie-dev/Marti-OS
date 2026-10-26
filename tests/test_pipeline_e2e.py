import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_full_happy_path_pipeline():
    # 1. intake
    intake_payload = {
        "patient_id": "PATIENT-TEST-01",
        "age": 30,
        "weight_kg": 70.0,
        "vitals": {
            "hr": 76,
            "sbp": 120,
            "dbp": 80,
            "spo2": 99,
            "temp_c": 37.8,
        },
        "symptoms": ["fever"],
        "free_text": "mild fever since morning",
        "allergies": [],
        "current_meds": [],
    }
    res_intake = client.post("/api/v1/intake", json=intake_payload)
    assert res_intake.status_code == 201
    encounter_id = res_intake.json()["encounter_id"]
    assert res_intake.json()["status"] == "VALIDATED"

    # 2. automated triage
    res_triage = client.post(f"/api/v1/review/process-triage/{encounter_id}")
    assert res_triage.status_code == 200
    assert res_triage.json()["status"] == "PENDING_REVIEW"
    assert len(res_triage.json()["medications"]) > 0

    # 3. doctor sign-off gate
    sign_off_payload = {
        "doctor_id": "DR-TEST-99",
        "decision": "APPROVE",
        "doctor_notes": "approved paracetamol protocol",
    }
    res_signoff = client.post(
        f"/api/v1/review/{encounter_id}/sign-off",
        json=sign_off_payload,
    )
    assert res_signoff.status_code == 200
    assert res_signoff.json()["status"] == "APPROVED"

    # 4. billing invoice
    res_billing = client.post(f"/api/v1/fulfillment/billing/{encounter_id}")
    assert res_billing.status_code == 200
    assert res_billing.json()["total_amount_inr"] >= 250.0

    # 5. cabinet dispense
    res_dispense = client.post(f"/api/v1/fulfillment/dispense/{encounter_id}")
    assert res_dispense.status_code == 200
    assert res_dispense.json()["is_dispensed"] is True
    assert len(res_dispense.json()["pickup_code"]) == 6

    # 6. verify cannot re-dispense (state machine check)
    res_double_dispense = client.post(f"/api/v1/fulfillment/dispense/{encounter_id}")
    assert res_double_dispense.status_code == 400

    # 7. fhir export
    res_fhir = client.get(f"/api/v1/fulfillment/fhir-export/{encounter_id}")
    assert res_fhir.status_code == 200
    bundle = res_fhir.json()
    assert bundle["resourceType"] == "Bundle"
    assert len(bundle["entry"]) == 4

def test_safety_escalation_blocks_physician_approval():
    # emergency vitals must not proceed through normal review
    emergency_payload = {
        "patient_id": "PATIENT-CRITICAL",
        "age": 45,
        "weight_kg": 80.0,
        "vitals": {
            "hr": 140,
            "sbp": 70,
            "dbp": 40,
            "spo2": 82,
            "temp_c": 39.5,
        },
        "symptoms": ["chest pain", "shortness of breath"],
        "free_text": "severe distress",
        "allergies": [],
        "current_meds": [],
    }
    res_intake = client.post("/api/v1/intake", json=emergency_payload)
    assert res_intake.status_code == 201
    data = res_intake.json()
    assert data["status"] == "ESCALATED"
    encounter_id = data["encounter_id"]

    # triage should reject processing escalated encounter
    res_triage = client.post(f"/api/v1/review/process-triage/{encounter_id}")
    assert res_triage.status_code == 400
def test_abdm_health_id_verification_success():
    payload = {"abha_number": "91-4567-8901-2345"}
    res = client.post("/api/v1/abdm/verify", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "VERIFIED"
    assert res.json()["profile"]["full_name"] == "Aman Verma"

def test_abdm_health_id_invalid_format():
    payload = {"abha_number": "12345"}
    res = client.post("/api/v1/abdm/verify", json=payload)
    assert res.status_code == 400