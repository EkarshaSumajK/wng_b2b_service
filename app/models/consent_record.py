from sqlalchemy import Column, String, ForeignKey, DateTime, Enum as SQLEnum, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class ConsentType(str, enum.Enum):
    ASSESSMENT = "ASSESSMENT"
    INTERVENTION = "INTERVENTION"
    DATA_SHARING = "DATA_SHARING"
    AI_ANALYSIS = "AI_ANALYSIS"


class ConsentStatus(str, enum.Enum):
    GRANTED = "GRANTED"
    PENDING = "PENDING"
    DENIED = "DENIED"
    REVOKED = "REVOKED"


class ConsentRecord(Base):
    __tablename__ = "b2b_consent_records"
    
    consent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False)
    parent_name = Column(String(200), nullable=True)
    consent_type = Column(SQLEnum(ConsentType), nullable=False)
    status = Column(SQLEnum(ConsentStatus), nullable=False, default=ConsentStatus.PENDING)
    granted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    documents = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = relationship("User", back_populates="consent_records")
