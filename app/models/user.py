from sqlalchemy import Column, String, JSON, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class UserRole(str, enum.Enum):
    COUNSELLOR = "COUNSELLOR"
    TEACHER = "TEACHER"
    PRINCIPAL = "PRINCIPAL"
    PARENT = "PARENT"
    CLINICIAN = "CLINICIAN"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "b2b_users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("b2b_schools.school_id"), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)  # Legacy column
    password_hash = Column(String(255), nullable=True)  # New column (matches admin platform)
    display_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    profile_picture_url = Column(String, nullable=True)
    profile = Column(JSON, nullable=True)
    availability = Column(JSON, nullable=True)
    auth_provider = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    school = relationship("School", back_populates="users")
    cases_created = relationship("Case", foreign_keys="Case.created_by", back_populates="creator")
    journal_entries = relationship("JournalEntry", back_populates="author")
    classes_taught = relationship("Class", foreign_keys="Class.teacher_id", back_populates="teacher")
    resources_authored = relationship("Resource", back_populates="author")
    observations_reported = relationship("Observation", back_populates="reporter")
    assessments_created = relationship("Assessment", back_populates="creator")
    activities_created = relationship("Activity", back_populates="creator")
    daily_boosters_created = relationship("DailyBooster", back_populates="creator")
    calendar_events_created = relationship("CalendarEvent", back_populates="creator")
    session_notes = relationship("SessionNote", back_populates="counsellor")
    risk_alerts_assigned = relationship("RiskAlert", foreign_keys="RiskAlert.assigned_to", back_populates="assigned_user")
    ai_recommendations_reviewed = relationship("AIRecommendation", foreign_keys="AIRecommendation.reviewed_by", back_populates="reviewer")
    webinar_registrations = relationship("WebinarRegistration", back_populates="user")
    therapist_bookings = relationship("TherapistBooking", back_populates="user")
