from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class RecommendationType(str, enum.Enum):
    INTERVENTION = "INTERVENTION"
    ASSESSMENT = "ASSESSMENT"
    REFERRAL = "REFERRAL"
    ALERT = "ALERT"


class ConfidenceLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AIRecommendation(Base):
    __tablename__ = "b2b_ai_recommendations"
    
    recommendation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(SQLEnum(RecommendationType), nullable=False)
    confidence = Column(SQLEnum(ConfidenceLevel), nullable=False)
    rationale = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=False)
    model_version = Column(String(50), nullable=True)
    related_student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=True)
    related_case_id = Column(UUID(as_uuid=True), ForeignKey("b2b_cases.case_id"), nullable=True)
    is_reviewed = Column(Boolean, default=False, nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    student = relationship("User", foreign_keys=[related_student_id], back_populates="ai_recommendations")
    case = relationship("Case", back_populates="ai_recommendations")
    reviewer = relationship("User", foreign_keys=[reviewed_by], back_populates="ai_recommendations_reviewed")
