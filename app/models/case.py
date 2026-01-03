from sqlalchemy import Column, String, Text, Boolean, JSON, ForeignKey, DateTime, Enum as SQLEnum, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class CaseStatus(str, enum.Enum):
    INTAKE = "INTAKE"
    ASSESSMENT = "ASSESSMENT"
    INTERVENTION = "INTERVENTION"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EntryVisibility(str, enum.Enum):
    PRIVATE = "PRIVATE"
    SHARED = "SHARED"


class EntryType(str, enum.Enum):
    SESSION_NOTE = "SESSION_NOTE"
    OBSERVATION = "OBSERVATION"
    ASSESSMENT_RESULT = "ASSESSMENT_RESULT"
    CONTACT_LOG = "CONTACT_LOG"


class Case(Base):
    __tablename__ = "b2b_cases"
    
    case_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_students.student_id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False)
    status = Column(SQLEnum(CaseStatus), nullable=False, default=CaseStatus.INTAKE)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False, default=RiskLevel.LOW)
    tags = Column(ARRAY(String), nullable=True)
    assigned_counsellor = Column(UUID(as_uuid=True), nullable=True)
    ai_summary = Column(Text, nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="cases")
    creator = relationship("User", foreign_keys=[created_by], back_populates="cases_created")
    journal_entries = relationship("JournalEntry", back_populates="case")
    session_notes = relationship("SessionNote", back_populates="case")
    goals = relationship("Goal", back_populates="case")
    ai_recommendations = relationship("AIRecommendation", back_populates="case")
    calendar_events = relationship("CalendarEvent", back_populates="case")


class JournalEntry(Base):
    __tablename__ = "b2b_journal_entries"
    
    entry_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("b2b_cases.case_id"), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False)
    visibility = Column(SQLEnum(EntryVisibility), nullable=False, default=EntryVisibility.SHARED)
    type = Column(SQLEnum(EntryType), nullable=False)
    content = Column(Text, nullable=True)
    audio_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    case = relationship("Case", back_populates="journal_entries")
    author = relationship("User", back_populates="journal_entries")
