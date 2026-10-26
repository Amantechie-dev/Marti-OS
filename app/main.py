from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.intake import router as intake_router
from app.api.review import router as review_router
from app.api.fulfillment import router as fulfillment_router
from app.api.abdm import router as abdm_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.encounter import TriageResult

app = FastAPI(title=settings.PROJECT_NAME)

# 1. Enable CORS so the frontend (port 5500) can communicate with FastAPI (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(intake_router)
app.include_router(review_router)
app.include_router(fulfillment_router)
app.include_router(abdm_router)

# 2. Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}

# 3. Endpoint for the frontend to fetch live queue data
@app.get("/api/v1/results")
def get_triage_results(db: Session = Depends(get_db)):
    results = db.query(TriageResult).order_by(TriageResult.id.desc()).limit(10).all()
    return results