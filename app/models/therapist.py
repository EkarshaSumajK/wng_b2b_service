from sqlalchemy import Column, String, Text, JSON, DateTime, Integer, Numeric, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class AvailabilityStatus(str, enum.Enum):
    AVAILABLE = "Available"
    LIMITED = "Limited"
    UNAVAILABLE = "Unavailable"


class Therapist(Base):
    __tablename__ = "b2b_therapists"
    
    therapist_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    name = Column(String, nullable=False, index=True)
    specialty = Column(String, nullable=False, index=True)
    bio = Column(Text, nullable=True)
    
    rating = Column(Numeric(3, 2), nullable=False, default=0.0)
    review_count = Column(Integer, nullable=False, default=0)
    
    location = Column(String, nullable=False, index=True)
    city = Column(String, nullable=False, index=True)
    state = Column(String, nullable=True)
    distance_km = Column(Numeric(10, 2), nullable=True)
    
    experience_years = Column(Integer, nullable=False)
    languages = Column(JSON, nullable=False)
    
    availability_status = Column(SQLEnum(AvailabilityStatus), nullable=False, default=AvailabilityStatus.AVAILABLE, index=True)
    consultation_fee_min = Column(Numeric(10, 2), nullable=False)
    consultation_fee_max = Column(Numeric(10, 2), nullable=False)
    
    qualifications = Column(JSON, nullable=True)
    areas_of_expertise = Column(JSON, nullable=True)
    
    profile_image_url = Column(String, nullable=True)
    
    verified = Column(Boolean, nullable=False, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = relationship("TherapistBooking", back_populates="therapist", cascade="all, delete-orphan")
