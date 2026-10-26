from app.core.redis import redis_client
from app.schemas.intake import IntakeCreate

STREAM_ROUTINE = "stream:triage:routine"
STREAM_URGENT = "stream:triage:urgent"

def route_encounter(encounter_id: str, intake: IntakeCreate) -> str:
    # children under 5, seniors over 65, or high fever get high priority
    is_urgent = (
        intake.age < 5
        or intake.age > 65
        or intake.vitals.temp_c >= 39.0
        or intake.vitals.hr > 110
        or intake.vitals.hr < 50
    )

    target_stream = STREAM_URGENT if is_urgent else STREAM_ROUTINE

    # publish event to redis stream
    redis_client.xadd(
        target_stream,
        {
            "encounter_id": encounter_id,
            "patient_id": intake.patient_id,
            "age": str(intake.age),
            "priority": "urgent" if is_urgent else "routine",
        },
    )

    return target_stream