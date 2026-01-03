from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Enum as SQLEnum, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class AlertLevel(str, enum.Enum):
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(str, enum.Enum):
    BEHAVIORAL = "BEHAVIORAL"
    ACADEMIC = "ACADEMIC"
    EMOTIONAL = "EMOTIONAL"
    SOCIAL = "SOCIAL"


class AlertStatus(str, enum.Enum):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"


class RiskAlert(Base):
    __tablename__ = "b2b_risk_alerts"
    
    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_students.student_id"), nullable=False)
    level = Column(SQLEnum(AlertLevel), nullable=False)
    type = Column(SQLEnum(AlertType), nullable=False)
    description = Column(Text, nullable=False)
    triggers = Column(ARRAY(String), nullable=True)
    recommendations = Column(ARRAY(String), nullable=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=True)
    status = Column(SQLEnum(AlertStatus), nullable=False, default=AlertStatus.NEW)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = relationship("Student", back_populates="risk_alerts")
    assigned_user = relationship("User", foreign_keys=[assigned_to], back_populates="risk_alerts_assigned")
