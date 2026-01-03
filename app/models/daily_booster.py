from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, Enum as SQLEnum, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.models.base import Base


class BoosterType(str, enum.Enum):
    STORY = "STORY"
    PUZZLE = "PUZZLE"
    MOVEMENT = "MOVEMENT"


class DifficultyLevel(str, enum.Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    ENGAGING = "ENGAGING"


class DailyBooster(Base):
    __tablename__ = "b2b_daily_boosters"
    
    booster_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("b2b_schools.school_id"), nullable=True)
    title = Column(String(200), nullable=False)
    type = Column(SQLEnum(BoosterType), nullable=False)
    duration = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    purpose = Column(Text, nullable=True)
    target_grades = Column(ARRAY(String), nullable=True)
    difficulty = Column(SQLEnum(DifficultyLevel), nullable=False)
    full_instructions = Column(Text, nullable=False)
    materials = Column(ARRAY(String), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    school = relationship("School", back_populates="daily_boosters")
    creator = relationship("User", back_populates="daily_boosters_created")
