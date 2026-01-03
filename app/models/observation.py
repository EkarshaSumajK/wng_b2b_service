from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class Severity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Observation(Base):
    __tablename__ = "b2b_observations"
    
    observation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_students.student_id"), nullable=False)
    reported_by = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False)
    severity = Column(SQLEnum(Severity), nullable=False)
    category = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    audio_url = Column(String, nullable=True)
    ai_summary = Column(Text, nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="observations")
    reporter = relationship("User", foreign_keys=[reported_by], back_populates="observations_reported")
