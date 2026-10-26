import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Enum,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class EncounterStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    VALIDATED = "VALIDATED"
    ESCALATED = "ESCALATED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISPENSED = "DISPENSED"
    FULFILLED = "FULFILLED"


def utc_now():
    return datetime.now(timezone.utc)


class Encounter(Base):
    __tablename__ = "encounters"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, nullable=False, index=True)
    status = Column(
        Enum(EncounterStatus),
        default=EncounterStatus.VALIDATED,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    intake = relationship("IntakeRecord", back_populates="encounter", uselist=False)
    triage_result = relationship("TriageResult", back_populates="encounter", uselist=False)
    approval = relationship("ApprovalRecord", back_populates="encounter", uselist=False)
    audit_logs = relationship("AuditLog", back_populates="encounter")


class IntakeRecord(Base):
    __tablename__ = "intake_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_id = Column(String, ForeignKey("encounters.id"), nullable=False, unique=True)
    age = Column(Integer, nullable=False)
    weight_kg = Column(Float, nullable=False)
    vitals = Column(JSON, nullable=False)
    symptoms = Column(JSON, nullable=False)
    free_text = Column(String, nullable=True)
    allergies = Column(JSON, default=list)
    current_meds = Column(JSON, default=list)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    encounter = relationship("Encounter", back_populates="intake")


class TriageResult(Base):
    __tablename__ = "triage_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_id = Column(String, ForeignKey("encounters.id"), nullable=False, unique=True)
    severity = Column(String, nullable=False)
    draft_note = Column(String, nullable=False)
    draft_prescription = Column(JSON, nullable=True)
    model_version = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    encounter = relationship("Encounter", back_populates="triage_result")


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_id = Column(String, ForeignKey("encounters.id"), nullable=False, unique=True)
    doctor_id = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    final_prescription = Column(JSON, nullable=True)
    doctor_notes = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    encounter = relationship("Encounter", back_populates="approval")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_id = Column(String, ForeignKey("encounters.id"), nullable=False)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    encounter = relationship("Encounter", back_populates="audit_logs")