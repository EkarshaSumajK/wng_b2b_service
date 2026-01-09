from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class AssignmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ActivityAssignment(Base):
    __tablename__ = "b2b_activity_assignments"
    
    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Activity ID - FK constraint exists in database to activities.activity_id
    # Not defined in SQLAlchemy model since activities table is in activity engine
    activity_id = Column(String, nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("b2b_classes.class_id"), nullable=False)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False)
    due_date = Column(DateTime, nullable=True)
    status = Column(SQLEnum(AssignmentStatus), default=AssignmentStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    class_obj = relationship("Class")
    assigner = relationship("User")
    submissions = relationship("ActivitySubmission", back_populates="assignment")
