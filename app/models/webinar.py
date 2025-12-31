from sqlalchemy import Column, String, Text, JSON, ForeignKey, DateTime, Enum as SQLEnum, Integer, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.core.database import Base


class WebinarCategory(str, enum.Enum):
    STUDENT_WELLBEING = "Student Wellbeing"
    MENTAL_HEALTH = "Mental Health"
    CRISIS_MANAGEMENT = "Crisis Management"
    PROFESSIONAL_DEVELOPMENT = "Professional Development"
    COMMUNICATION = "Communication"
    SELF_CARE = "Self-Care"
    SAFETY = "Safety"
    LEARNING_DISABILITIES = "Learning Disabilities"
    COUNSELING_SKILLS = "Counseling Skills"
    CURRICULUM = "Curriculum"
    INCLUSION = "Inclusion"


class WebinarStatus(str, enum.Enum):
    UPCOMING = "Upcoming"
    LIVE = "Live"
    RECORDED = "Recorded"
    CANCELLED = "Cancelled"


class WebinarLevel(str, enum.Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    ALL_LEVELS = "All Levels"


class WebinarAudience(str, enum.Enum):
    STUDENTS = "Students"
    TEACHERS = "Teachers"
    PARENTS = "Parents"
    COUNSELLORS = "Counsellors"
    ALL = "All"


class Webinar(Base):
    __tablename__ = "webinars"
    
    webinar_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Assignment - school/class targeting
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.school_id"), nullable=True, index=True)
    class_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # Specific classes (null = all classes in school)
    target_audience = Column(SQLEnum(WebinarAudience, values_callable=lambda x: [e.value for e in x]), nullable=True, default=WebinarAudience.STUDENTS)
    target_grades = Column(ARRAY(String), nullable=True)  # e.g., ["8", "9", "10"]
    
    # Speaker information
    speaker_name = Column(String, nullable=False)
    speaker_title = Column(String, nullable=True)
    speaker_bio = Column(Text, nullable=True)
    speaker_image_url = Column(String, nullable=True)
    
    # Scheduling
    date = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False)
    
    # Classification
    category = Column(SQLEnum(WebinarCategory), nullable=False, index=True)
    status = Column(SQLEnum(WebinarStatus), nullable=False, default=WebinarStatus.UPCOMING, index=True)
    level = Column(SQLEnum(WebinarLevel), nullable=False)
    
    # Pricing
    price = Column(Numeric(10, 2), nullable=False, default=0)  # 0 means free
    
    # Content
    topics = Column(JSON, nullable=True)  # Array of topic strings
    video_url = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    
    # Capacity and metrics
    max_attendees = Column(Integer, nullable=True)  # Null = unlimited
    attendee_count = Column(Integer, default=0)
    views = Column(Integer, default=0)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    school = relationship("School")
    creator = relationship("User")
    registrations = relationship("WebinarRegistration", back_populates="webinar", cascade="all, delete-orphan")
    student_attendance = relationship("StudentWebinarAttendance", back_populates="webinar")


class RegistrationType(str, enum.Enum):
    SCHOOL = "school"
    CLASS = "class"


class RegistrationStatus(str, enum.Enum):
    ACTIVE = "Active"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class WebinarSchoolRegistration(Base):
    """Tracks school-level webinar registrations with class/grade targeting."""
    __tablename__ = "webinar_school_registrations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webinar_id = Column(UUID(as_uuid=True), ForeignKey("webinars.webinar_id"), nullable=False, index=True)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.school_id"), nullable=False, index=True)
    registration_type = Column(SQLEnum(RegistrationType), nullable=False, default=RegistrationType.SCHOOL)
    class_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True, default=[])
    grade_ids = Column(ARRAY(String), nullable=True, default=[])
    registered_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    status = Column(SQLEnum(RegistrationStatus), nullable=False, default=RegistrationStatus.ACTIVE, index=True)
    total_students_invited = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    webinar = relationship("Webinar", backref="school_registrations")
    school = relationship("School")
    registered_by_user = relationship("User")
    
    __table_args__ = (
        # Unique constraint: one registration per school per webinar
        {'sqlite_autoincrement': True},
    )
