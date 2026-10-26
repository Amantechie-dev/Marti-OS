import os
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

TRIAGE_STREAM_KEY = "marti:stream:triage"
TRIAGE_GROUP_NAME = "triage_workers"

def get_redis_client():
    return redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        protocol=2,
    )

# alias global client instance for modules importing redis_client directly
redis_client = get_redis_client()

def init_redis_stream():
    client = get_redis_client()
    try:
        client.xgroup_create(
            name=TRIAGE_STREAM_KEY,
            groupname=TRIAGE_GROUP_NAME,
            id="0",
            mkstream=True,
        )
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise e