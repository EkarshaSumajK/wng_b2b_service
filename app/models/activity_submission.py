from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class SubmissionStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class FileType(str, enum.Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    OTHER = "OTHER"


class ActivitySubmission(Base):
    __tablename__ = "b2b_activity_submissions"
    
    submission_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("b2b_activity_assignments.assignment_id"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False)
    file_url = Column(String, nullable=True)
    file_type = Column(SQLEnum(FileType), nullable=True)
    status = Column(SQLEnum(SubmissionStatus), default=SubmissionStatus.PENDING)
    feedback = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assignment = relationship("ActivityAssignment", back_populates="submissions")
    student = relationship("User")
    comments = relationship("SubmissionComment", back_populates="submission", cascade="all, delete-orphan")


class SubmissionComment(Base):
    __tablename__ = "b2b_submission_comments"
    
    comment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("b2b_activity_submissions.submission_id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    submission = relationship("ActivitySubmission", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])
    student = relationship("User", foreign_keys=[student_id])
