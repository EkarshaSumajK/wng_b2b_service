from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class GoalStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"


class Goal(Base):
    __tablename__ = "b2b_goals"
    
    goal_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("b2b_cases.case_id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    target_date = Column(DateTime, nullable=True)
    status = Column(SQLEnum(GoalStatus), nullable=False, default=GoalStatus.NOT_STARTED)
    progress = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    case = relationship("Case", back_populates="goals")
