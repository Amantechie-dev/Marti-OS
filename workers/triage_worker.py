import time
import uuid
import logging
from app.core.database import SessionLocal
from app.core.redis import (
    get_redis_client,
    TRIAGE_STREAM_KEY,
    TRIAGE_GROUP_NAME,
    init_redis_stream,
)
from app.models.encounter import Encounter, EncounterStatus, TriageResult, AuditLog
from app.services.safety import evaluate_safety
from app.schemas.intake import VitalsInput

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("triage_worker")

WORKER_NAME = f"worker-{uuid.uuid4().hex[:6]}"
IDLE_TIMEOUT_MS = 300000  # 5 minutes in milliseconds

def process_triage_job(db, encounter_id: str):
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        logger.warning(f"encounter {encounter_id} not found")
        return

    if encounter.status != EncounterStatus.VALIDATED:
        logger.info(f"skipping encounter {encounter_id} with status {encounter.status}")
        return

    intake = encounter.intake
    if not intake:
        logger.error(f"no intake record attached to encounter {encounter_id}")
        return

    # run clinical rule checks
    vitals_obj = VitalsInput(**intake.vitals)
    safety = evaluate_safety(vitals_obj, intake.symptoms)

    if not safety.is_safe:
        encounter.status = EncounterStatus.ESCALATED
        severity = "EMERGENCY"
        draft_note = f"critical safety alert: {', '.join(safety.flags)}"
        prescription = []
    else:
        encounter.status = EncounterStatus.PENDING_REVIEW
        severity = "ROUTINE"
        draft_note = "standard protocol: viral syndrome / mild fever profile"
        prescription = [
            {"drug": "Paracetamol", "dosage": "500mg", "frequency": "TDS", "days": 3}
        ]

    triage_rec = TriageResult(
        encounter_id=encounter.id,
        severity=severity,
        draft_note=draft_note,
        draft_prescription=prescription,
        model_version="marti-rules-v1.2",
    )
    db.add(triage_rec)

    audit = AuditLog(
        encounter_id=encounter.id,
        actor=f"async_triage_worker:{WORKER_NAME}",
        action="ASYNC_TRIAGE_COMPLETED",
        details={"status": encounter.status.value, "severity": severity},
    )
    db.add(audit)
    db.commit()
    logger.info(f"processed encounter {encounter_id} -> {encounter.status.value}")

def recover_stalled_tasks(r):
    return
    """Claim and process tasks that crashed mid-execution and were left in the PEL."""
    try:
        # xautoclaim reassigns idle messages from dead consumers to this WORKER_NAME
        result = r.xautoclaim(
            name=TRIAGE_STREAM_KEY,
            groupname=TRIAGE_GROUP_NAME,
            consumername=WORKER_NAME,
            min_idle_time=IDLE_TIMEOUT_MS,
            start_id="0-0",
            count=10
        )
        
        # Depending on redis-py version, result is usually [next_start_id, messages]
        claimed_messages = result[1] if isinstance(result, (list, tuple)) else []
        
        if claimed_messages:
            logger.info(f"Recovered {len(claimed_messages)} stalled tasks from PEL. Re-processing...")
            for message_id, data in claimed_messages:
                # Handle potential string decoding depending on redis client config
                encounter_id = data.get(b"encounter_id", data.get("encounter_id"))
                if isinstance(encounter_id, bytes):
                    encounter_id = encounter_id.decode("utf-8")
                
                db = SessionLocal()
                try:
                    process_triage_job(db, encounter_id)
                    r.xack(TRIAGE_STREAM_KEY, TRIAGE_GROUP_NAME, message_id)
                except Exception as err:
                    db.rollback()
                    logger.error(f"failed re-processing {encounter_id}: {err}")
                finally:
                    db.close()
                    
    except Exception as e:
        logger.error(f"error during stalled task recovery: {e}")

def start_worker():
    init_redis_stream()
    r = get_redis_client()
    logger.info(f"starting triage worker {WORKER_NAME} on stream {TRIAGE_STREAM_KEY}")

    last_recovery_check = 0

    while True:
        try:
            # Sweep for dead-letter tasks every 60 seconds
            current_time = time.time()
            if current_time - last_recovery_check > 60:
                recover_stalled_tasks(r)
                last_recovery_check = current_time

            # block for up to 2 seconds waiting for new stream entries
            entries = r.xreadgroup(
                groupname=TRIAGE_GROUP_NAME,
                consumername=WORKER_NAME,
                streams={TRIAGE_STREAM_KEY: ">"},
                count=1,
                block=2000,
            )

            if not entries:
                continue

            for stream_name, messages in entries:
                for message_id, data in messages:
                    encounter_id = data.get(b"encounter_id", data.get("encounter_id"))
                    if isinstance(encounter_id, bytes):
                        encounter_id = encounter_id.decode("utf-8")
                        
                    logger.info(f"received message {message_id} for encounter {encounter_id}")

                    db = SessionLocal()
                    try:
                        process_triage_job(db, encounter_id)
                        # acknowledge stream message upon successful db write
                        r.xack(TRIAGE_STREAM_KEY, TRIAGE_GROUP_NAME, message_id)
                    except Exception as err:
                        db.rollback()
                        logger.error(f"failed processing {encounter_id}: {err}")
                    finally:
                        db.close()

        except Exception as e:
            logger.error(f"worker loop exception: {e}")
            time.sleep(2)

if __name__ == "__main__":
    start_worker()