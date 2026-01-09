"""
Student engagement tracking models.
Tracks app sessions, daily streaks, and webinar attendance.
"""
from sqlalchemy import Column, String, Integer, Boolean, Date, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.models.base import Base


class StudentAppSession(Base):
    """Tracks individual app sessions for students."""
    __tablename__ = "b2b_student_app_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False, index=True)
    session_start = Column(DateTime, nullable=False)
    session_end = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    student = relationship("User")


class StudentDailyStreak(Base):
    """Tracks daily activity for streak calculation."""
    __tablename__ = "b2b_student_daily_streaks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    app_opened = Column(Boolean, default=False)
    app_open_time = Column(DateTime, nullable=True)
    activity_completed = Column(Boolean, default=False)
    activities_count = Column(Integer, default=0)
    streak_maintained = Column(Boolean, default=False)
    
    __table_args__ = (
        UniqueConstraint('student_id', 'date', name='uq_b2b_student_daily_streak'),
    )
    
    # Relationships
    student = relationship("User")


class StudentStreakSummary(Base):
    """Denormalized streak summary for performance."""
    __tablename__ = "b2b_student_streak_summary"
    
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), primary_key=True)
    current_streak = Column(Integer, default=0)
    max_streak = Column(Integer, default=0)
    streak_start_date = Column(Date, nullable=True)
    last_active_date = Column(Date, nullable=True)
    total_active_days = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = relationship("User")


class StudentWebinarAttendance(Base):
    """Tracks student webinar attendance."""
    __tablename__ = "b2b_student_webinar_attendance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webinar_id = Column(UUID(as_uuid=True), ForeignKey("b2b_webinars.webinar_id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False, index=True)
    attended = Column(Boolean, default=False)
    join_time = Column(DateTime, nullable=True)
    leave_time = Column(DateTime, nullable=True)
    watch_duration_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('webinar_id', 'student_id', name='uq_b2b_webinar_student_attendance'),
    )
    
    # Relationships
    webinar = relationship("Webinar", back_populates="student_attendance")
    student = relationship("User")
