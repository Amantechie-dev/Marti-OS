
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.redis import get_redis_client, TRIAGE_STREAM_KEY
from app.models.encounter import Encounter, EncounterStatus
from app.core.database import SessionLocal
import workers.triage_worker as worker

client = TestClient(app)

def test_pel_recovery_after_crash():
    r = get_redis_client()
    
    # 1. Generate a totally unique consumer group just for this test
    TEST_GROUP = f"test-group-{uuid.uuid4().hex[:6]}"
    
    try:
        # Create it pointing at "$" so it only listens for NEW messages
        try:
            r.xgroup_create(TRIAGE_STREAM_KEY, TEST_GROUP, id="$", mkstream=True)
        except Exception:
            pass
        
        db_session = SessionLocal()
        
        try:
            test_patient = f"PATIENT-CRASH-{uuid.uuid4().hex[:6]}"
            
            # 2. Submit intake (publishes to stream)
            intake_data = {
                "patient_id": test_patient,
                "age": 30,
                "weight_kg": 70.0,
                "vitals": {"hr": 80.0, "sbp": 120.0, "dbp": 80.0, "spo2": 98.0, "temp_c": 37.0},
                "symptoms": ["cough"],
                "free_text": "crash recovery test",
                "allergies": [],
                "current_meds": [],
                "abha_number": "91-0000-0000-0000"
            }
            res = client.post("/api/v1/intake/", json=intake_data)
            assert res.status_code == 201, f"API failed with {res.text}"
            encounter_id = res.json()["encounter_id"]
            
            # 3. Safely read from our isolated group (rogue workers cannot steal from this group)
            entries = r.xreadgroup(
                groupname=TEST_GROUP,
                consumername="doomed-test-worker",
                streams={TRIAGE_STREAM_KEY: ">"},
                count=1,
                block=1000
            )
            assert entries, "Stream entry was not delivered to the test consumer group"
            
            db_encounter = db_session.query(Encounter).filter(Encounter.id == encounter_id).first()
            assert db_encounter.status == EncounterStatus.VALIDATED
            
            # 4. Patch the worker to use our test group, and trigger recovery
            with patch.object(worker, 'TRIAGE_GROUP_NAME', TEST_GROUP):
                with patch.object(worker, 'IDLE_TIMEOUT_MS', 0):
                    worker.recover_stalled_tasks(r)
                    
            # 5. Verify the worker successfully saved the encounter
            db_session.refresh(db_encounter)
            assert db_encounter.status == EncounterStatus.PENDING_REVIEW
            
        finally:
            db_session.close()
            
    finally:
        # Clean up the test group from Redis so we don't leave trash behind
        r.xgroup_destroy(TRIAGE_STREAM_KEY, TEST_GROUP)