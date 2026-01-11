from sqlalchemy import Column, String, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.models.base import Base


class Class(Base):
    __tablename__ = "b2b_classes"
    
    class_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("b2b_schools.school_id"), nullable=False)
    name = Column(String, nullable=False)
    grade = Column(String, nullable=False)
    section = Column(String, nullable=True)
    academic_year = Column(String, nullable=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("b2b_users.user_id"), nullable=True)
    capacity = Column(Integer, nullable=True)
    additional_info = Column(JSON, nullable=True)
    
    # Relationships
    school = relationship("School", back_populates="classes")
    teacher = relationship("User", foreign_keys=[teacher_id], back_populates="classes_taught")
    students = relationship("Student", back_populates="class_obj")
