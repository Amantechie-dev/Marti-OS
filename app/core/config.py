import os
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "marti"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+psycopg2://postgres:Aman$1ngh@localhost:5432/marti_db"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

settings = Settings()