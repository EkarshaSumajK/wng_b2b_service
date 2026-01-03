from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, Enum as SQLEnum, ARRAY, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class ActivityType(str, enum.Enum):
    PHYSICAL_DEVELOPMENT = "PHYSICAL_DEVELOPMENT"
    COGNITIVE_DEVELOPMENT = "COGNITIVE_DEVELOPMENT"
    SOCIAL_EMOTIONAL_DEVELOPMENT = "SOCIAL_EMOTIONAL_DEVELOPMENT"
    LANGUAGE_COMMUNICATION_DEVELOPMENT = "LANGUAGE_COMMUNICATION_DEVELOPMENT"


class LocationType(str, enum.Enum):
    IN_CLASS = "IN_CLASS"
    AT_HOME = "AT_HOME"
    OTHER = "OTHER"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SkillLevel(str, enum.Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class Activity(Base):
    __tablename__ = "b2b_activities"
    
    activity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("b2b_schools.school_id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(SQLEnum(ActivityType), nullable=False)
    thumbnail_url = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    target_grades = Column(ARRAY(String), nullable=True)
    materials = Column(ARRAY(String), nullable=True)
    instructions = Column(ARRAY(Text), nullable=True)
    objectives = Column(ARRAY(String), nullable=True)
    diagnosis = Column(ARRAY(String), nullable=True)
    location = Column(SQLEnum(LocationType), nullable=True)
    risk_level = Column(SQLEnum(RiskLevel), nullable=True)
    skill_level = Column(SQLEnum(SkillLevel), nullable=True)
    theme = Column(ARRAY(String), nullable=True)
    is_counselor_only = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    school = relationship("School", back_populates="activities")
    creator = relationship("User", back_populates="activities_created")
