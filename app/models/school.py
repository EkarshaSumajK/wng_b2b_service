from sqlalchemy import Column, String, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.models.base import Base


class School(Base):
    __tablename__ = "b2b_schools"
    
    school_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    timezone = Column(String, nullable=False, default="UTC")
    academic_year = Column(String, nullable=True)
    data_retention_policy = Column(JSON, nullable=True)
    settings = Column(JSON, nullable=True)
    logo_url = Column(String, nullable=True)
    
    # Relationships
    users = relationship("User", back_populates="school")
    students = relationship("Student", back_populates="school")
    classes = relationship("Class", back_populates="school")
    resources = relationship("Resource", back_populates="school")
    activities = relationship("Activity", back_populates="school")
    daily_boosters = relationship("DailyBooster", back_populates="school")
    calendar_events = relationship("CalendarEvent", back_populates="school")
