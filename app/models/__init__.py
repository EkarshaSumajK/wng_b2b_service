# Models - Using Auth DB (b2b_ prefixed tables)
from app.models.base import Base

# Core entities
from app.models.school import School
from app.models.user import User, UserRole
from app.models.student import Student, Gender, RiskLevel, ConsentStatus
from app.models.class_model import Class

# Cases
from app.models.case import Case, JournalEntry, CaseStatus, RiskLevel as CaseRiskLevel, EntryVisibility, EntryType

# Assessments
from app.models.assessment import Assessment, AssessmentTemplate, StudentResponse, QuestionType

# Observations
from app.models.observation import Observation, Severity

# Resources
from app.models.resource import Resource, ResourceType, ResourceStatus

# Activities
from app.models.activity import Activity, ActivityType, LocationType, RiskLevel as ActivityRiskLevel, SkillLevel
from app.models.activity_assignment import ActivityAssignment, AssignmentStatus
from app.models.activity_submission import ActivitySubmission, SubmissionComment, SubmissionStatus, FileType

# Risk & AI
from app.models.risk_alert import RiskAlert, AlertLevel, AlertType, AlertStatus
from app.models.ai_recommendation import AIRecommendation, RecommendationType, ConfidenceLevel

# Consent
from app.models.consent_record import ConsentRecord, ConsentType, ConsentStatus as ConsentRecordStatus

# Goals
from app.models.goal import Goal, GoalStatus

# Daily Boosters
from app.models.daily_booster import DailyBooster, BoosterType, DifficultyLevel

# Calendar
from app.models.calendar_event import CalendarEvent, EventType, EventStatus

# Session Notes
from app.models.session_note import SessionNote, SessionType

# Webinars
from app.models.webinar import (
    Webinar, WebinarSchoolRegistration, WebinarCategory, WebinarStatus,
    WebinarLevel, WebinarAudience, RegistrationType, RegistrationStatus
)
from app.models.webinar_registration import WebinarRegistration, RegistrationStatus as WebinarRegistrationStatus

# Therapists
from app.models.therapist import Therapist, AvailabilityStatus
from app.models.therapist_booking import TherapistBooking, BookingStatus

# Student Engagement
from app.models.student_engagement import (
    StudentAppSession,
    StudentDailyStreak,
    StudentStreakSummary,
    StudentWebinarAttendance
)

__all__ = [
    # Base
    "Base",
    
    # Core entities
    "School",
    "User",
    "UserRole",
    "Student",
    "Gender",
    "RiskLevel",
    "ConsentStatus",
    "Class",
    
    # Cases
    "Case",
    "JournalEntry",
    "CaseStatus",
    "CaseRiskLevel",
    "EntryVisibility",
    "EntryType",
    
    # Assessments
    "Assessment",
    "AssessmentTemplate",
    "StudentResponse",
    "QuestionType",
    
    # Observations
    "Observation",
    "Severity",
    
    # Resources
    "Resource",
    "ResourceType",
    "ResourceStatus",
    
    # Activities
    "Activity",
    "ActivityType",
    "LocationType",
    "ActivityRiskLevel",
    "SkillLevel",
    "ActivityAssignment",
    "AssignmentStatus",
    "ActivitySubmission",
    "SubmissionComment",
    "SubmissionStatus",
    "FileType",
    
    # Risk & AI
    "RiskAlert",
    "AlertLevel",
    "AlertType",
    "AlertStatus",
    "AIRecommendation",
    "RecommendationType",
    "ConfidenceLevel",
    
    # Consent
    "ConsentRecord",
    "ConsentType",
    "ConsentRecordStatus",
    
    # Goals
    "Goal",
    "GoalStatus",
    
    # Daily Boosters
    "DailyBooster",
    "BoosterType",
    "DifficultyLevel",
    
    # Calendar
    "CalendarEvent",
    "EventType",
    "EventStatus",
    
    # Session Notes
    "SessionNote",
    "SessionType",
    
    # Webinars
    "Webinar",
    "WebinarSchoolRegistration",
    "WebinarCategory",
    "WebinarStatus",
    "WebinarLevel",
    "WebinarAudience",
    "WebinarRegistration",
    "WebinarRegistrationStatus",
    "RegistrationType",
    "RegistrationStatus",
    
    # Therapists
    "Therapist",
    "AvailabilityStatus",
    "TherapistBooking",
    "BookingStatus",
    
    # Student Engagement
    "StudentAppSession",
    "StudentDailyStreak",
    "StudentStreakSummary",
    "StudentWebinarAttendance",
]
