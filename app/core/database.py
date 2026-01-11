from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Main database engine (b2b_ prefixed tables)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=5,
    pool_recycle=3600,
    echo=False,
    connect_args={
        "connect_timeout": 10,
    }
)

# Import Base from models
from app.models.base import Base

# Main session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Activity Database - uses separate DATABASE_URL_ACTIVITY if configured
activity_db_url = getattr(settings, 'DATABASE_URL_ACTIVITY', None) or settings.DATABASE_URL

activity_engine = create_engine(
    activity_db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=5,
    pool_recycle=3600,
    echo=False,
    connect_args={
        "connect_timeout": 10,
    }
)

ActivitySessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=activity_engine,
    expire_on_commit=False
)

def get_activity_db():
    """Get database session for activities (uses separate DB if configured)."""
    db = ActivitySessionLocal()
    try:
        yield db
    finally:
        db.close()


# Aliases for backward compatibility
auth_engine = engine
AuthSessionLocal = SessionLocal

# Alias for get_db - backward compatibility
get_auth_db = get_db


def create_tables():
    """Create all database tables (b2b_ prefixed tables)."""
    from app.models import (
        School, User, Student, Class, Case, JournalEntry,
        Assessment, AssessmentTemplate, StudentResponse, Observation,
        Resource, Activity, RiskAlert, AIRecommendation, ConsentRecord,
        Goal, DailyBooster, CalendarEvent, SessionNote, Webinar,
        WebinarSchoolRegistration, WebinarRegistration, Therapist,
        TherapistBooking, ActivityAssignment, ActivitySubmission,
        SubmissionComment, StudentAppSession, StudentDailyStreak,
        StudentStreakSummary, StudentWebinarAttendance
    )
    Base.metadata.create_all(bind=engine)
