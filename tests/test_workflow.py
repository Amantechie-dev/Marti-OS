import pytest
import time
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.core.redis import get_redis_client, TRIAGE_STREAM_KEY, TRIAGE_GROUP_NAME
from app.models.encounter import Encounter, EncounterStatus, TriageResult

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()

def test_full_clinical_pipeline(db_session):
    test_patient = f"PATIENT-TEST-{uuid.uuid4().hex[:6]}"

    # step 1: submit patient intake
    intake_data = {
        "patient_id": test_patient,
        "age": 28,
        "weight_kg": 62.0,
        "vitals": {
            "hr": 74.0,
            "sbp": 118.0,
            "dbp": 78.0,
            "spo2": 99.0,
            "temp_c": 37.1
        },
        "symptoms": ["headache", "fever"],
        "free_text": "mild headache and low fever since morning",
        "allergies": [],
        "current_meds": [],
        "abha_number": "91-1111-2222-3333"
    }

    res_intake = client.post("/api/v1/intake/", json=intake_data)
    assert res_intake.status_code == 201
    intake_json = res_intake.json()
    encounter_id = intake_json["encounter_id"]
    assert intake_json["status"] == "VALIDATED"

    # step 2: verify redis stream ingestion
    r = get_redis_client()
    stream_len = r.xlen(TRIAGE_STREAM_KEY)
    assert stream_len > 0

    # wait briefly for triage worker processing
    retries = 10
    encounter = None
    while retries > 0:
        db_session.expire_all()
        encounter = db_session.query(Encounter).filter(Encounter.id == encounter_id).first()
        if encounter and encounter.status == EncounterStatus.PENDING_REVIEW:
            break
        time.sleep(0.5)
        retries -= 1

    assert encounter is not None
    assert encounter.status == EncounterStatus.PENDING_REVIEW

    # step 3: query pending review queue
    res_queue = client.get("/api/v1/review/pending")
    assert res_queue.status_code == 200
    pending_ids = [item["encounter_id"] for item in res_queue.json()]
    assert encounter_id in pending_ids

    # step 4: submit physician decision
    review_data = {
        "physician_id": "DOC-AUTO-TEST",
        "decision": "APPROVE",
        "clinical_notes": "approved automated paracetamol regimen",
        "final_prescription": [
            {
                "drug": "Paracetamol",
                "dosage": "500mg",
                "frequency": "TDS",
                "days": 3,
                "quantity": 9
            }
        ]
    }
    res_review = client.post(f"/api/v1/review/{encounter_id}/decision", json=review_data)
    assert res_review.status_code == 200
    assert res_review.json()["status"] == "APPROVED"

    # step 5: execute medication dispensing
    dispense_data = {
        "dispensed_by": "ROBOT-DISP-01",
        "dispenser_slot": "SLOT-C1"
    }
    res_dispense = client.post(f"/api/v1/fulfillment/dispense/{encounter_id}", json=dispense_data)
    assert res_dispense.status_code == 200
    assert res_dispense.json()["status"] == "DISPENSED"

    # step 6: export fhir care context bundle
    res_fhir = client.get(f"/api/v1/fulfillment/fhir-export/{encounter_id}")
    assert res_fhir.status_code == 200
    bundle = res_fhir.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "document"
    assert len(bundle["entry"]) >= 4