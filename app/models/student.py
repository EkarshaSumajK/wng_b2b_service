from sqlalchemy import Column, String, Date, JSON, ForeignKey, Enum as SQLEnum, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from app.models.base import Base


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConsentStatus(str, enum.Enum):
    GRANTED = "GRANTED"
    PENDING = "PENDING"
    DENIED = "DENIED"


class Student(Base):
    __tablename__ = "b2b_students"
    
    student_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("b2b_schools.school_id"), nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    pseudonym = Column(String, nullable=True)
    roll_number = Column(String, nullable=True)
    username = Column(String, nullable=True, unique=True, index=True)  # For student/parent login
    email = Column(String, nullable=True)  # Student's email
    password_hash = Column(String, nullable=True)  # For student/parent login
    dob = Column(Date, nullable=True)
    gender = Column(SQLEnum(Gender), nullable=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("b2b_classes.class_id"), nullable=True)
    grade = Column(String, nullable=True)
    parents_id = Column(JSON, nullable=True)
    parent_email = Column(String, nullable=True)
    parent_phone = Column(String, nullable=True)
    risk_level = Column(SQLEnum(RiskLevel), nullable=True, default=RiskLevel.LOW)
    wellbeing_score = Column(Integer, nullable=True)
    last_assessment = Column(Date, nullable=True)
    consent_status = Column(SQLEnum(ConsentStatus), nullable=True, default=ConsentStatus.PENDING)
    notes = Column(Text, nullable=True)
    additional_info = Column(JSON, nullable=True)
    
    # Relationships
    school = relationship("School", back_populates="students")
    class_obj = relationship("Class", back_populates="students")
    # Note: cases, observations, risk_alerts, ai_recommendations, consent_records, 
    # calendar_events, and therapist_bookings relationships have been migrated to User model
