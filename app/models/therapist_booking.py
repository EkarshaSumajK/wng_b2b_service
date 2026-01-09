from sqlalchemy import Column, ForeignKey, DateTime, Enum as SQLEnum, Integer, Text, Date, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class BookingStatus(str, enum.Enum):
    REQUESTED = "Requested"
    CONFIRMED = "Confirmed"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"


class TherapistBooking(Base):
    __tablename__ = "b2b_therapist_bookings"
    
    booking_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    therapist_id = Column(UUID(as_uuid=True), ForeignKey("b2b_therapists.therapist_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    school_id = Column(UUID(as_uuid=True), ForeignKey("b2b_schools.school_id", ondelete="CASCADE"), nullable=False, index=True)
    
    appointment_date = Column(Date, nullable=False, index=True)
    appointment_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=60)
    
    status = Column(SQLEnum(BookingStatus), nullable=False, default=BookingStatus.REQUESTED, index=True)
    
    notes = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    therapist = relationship("Therapist", back_populates="bookings")
    user = relationship("User", foreign_keys=[user_id], back_populates="therapist_bookings")
    student = relationship("User", foreign_keys=[student_id], back_populates="therapist_bookings_as_student")
    school = relationship("School")
