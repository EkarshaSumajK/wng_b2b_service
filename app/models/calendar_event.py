from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Enum as SQLEnum, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class EventType(str, enum.Enum):
    SESSION = "SESSION"
    ASSESSMENT = "ASSESSMENT"
    MEETING = "MEETING"
    ACTIVITY = "ACTIVITY"
    REMINDER = "REMINDER"


class EventStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"


class CalendarEvent(Base):
    __tablename__ = "b2b_calendar_events"
    
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("b2b_schools.school_id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(SQLEnum(EventType), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(200), nullable=True)
    attendees = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    status = Column(SQLEnum(EventStatus), nullable=False, default=EventStatus.SCHEDULED)
    related_case_id = Column(UUID(as_uuid=True), ForeignKey("b2b_cases.case_id"), nullable=True)
    related_student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_students.student_id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    school = relationship("School", back_populates="calendar_events")
    case = relationship("Case", back_populates="calendar_events")
    student = relationship("Student", back_populates="calendar_events")
    creator = relationship("User", back_populates="calendar_events_created")
