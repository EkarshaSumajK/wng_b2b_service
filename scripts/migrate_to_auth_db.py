#!/usr/bin/env python3
"""
Script to migrate data from main DB to auth DB (b2b_ prefixed tables).
Drops existing tables, recreates them, and copies all data.

Usage:
    python scripts/migrate_to_auth_db.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import engine, auth_engine, SessionLocal, AuthSessionLocal
from app.models.auth.base import AuthBase

# Main DB Models
from app.models.school import School
from app.models.user import User
from app.models.student import Student
from app.models.class_model import Class
from app.models.case import Case, JournalEntry
from app.models.assessment import Assessment, AssessmentTemplate, StudentResponse
from app.models.observation import Observation
from app.models.resource import Resource
from app.models.activity import Activity
from app.models.risk_alert import RiskAlert
from app.models.ai_recommendation import AIRecommendation
from app.models.consent_record import ConsentRecord
from app.models.goal import Goal
from app.models.daily_booster import DailyBooster
from app.models.calendar_event import CalendarEvent
from app.models.session_note import SessionNote
from app.models.webinar import Webinar, WebinarSchoolRegistration
from app.models.webinar_registration import WebinarRegistration
from app.models.therapist import Therapist
from app.models.therapist_booking import TherapistBooking
from app.models.activity_assignment import ActivityAssignment
from app.models.activity_submission import ActivitySubmission, SubmissionComment
from app.models.student_engagement import (
    StudentAppSession, StudentDailyStreak, StudentStreakSummary, StudentWebinarAttendance
)

# Auth DB Models
from app.models.auth.school import B2BSchool
from app.models.auth.user import B2BUserAuth
from app.models.auth.student import B2BStudent
from app.models.auth.class_model import B2BClass
from app.models.auth.case import B2BCase, B2BJournalEntry
from app.models.auth.assessment import B2BAssessment, B2BAssessmentTemplate, B2BStudentResponse
from app.models.auth.observation import B2BObservation
from app.models.auth.resource import B2BResource
from app.models.auth.activity import B2BActivity
from app.models.auth.risk_alert import B2BRiskAlert
from app.models.auth.ai_recommendation import B2BAIRecommendation
from app.models.auth.consent_record import B2BConsentRecord
from app.models.auth.goal import B2BGoal
from app.models.auth.daily_booster import B2BDailyBooster
from app.models.auth.calendar_event import B2BCalendarEvent
from app.models.auth.session_note import B2BSessionNote
from app.models.auth.webinar import B2BWebinar, B2BWebinarSchoolRegistration
from app.models.auth.webinar_registration import B2BWebinarRegistration
from app.models.auth.therapist import B2BTherapist
from app.models.auth.therapist_booking import B2BTherapistBooking
from app.models.auth.activity_assignment import B2BActivityAssignment
from app.models.auth.activity_submission import B2BActivitySubmission, B2BSubmissionComment
from app.models.auth.student_engagement import (
    B2BStudentAppSession, B2BStudentDailyStreak, B2BStudentStreakSummary, B2BStudentWebinarAttendance
)


def drop_and_recreate_tables():
    """Drop all b2b_ tables and recreate them with correct schema."""
    print("\n[Dropping and recreating tables]")
    
    print("  Dropping existing b2b_ tables...")
    AuthBase.metadata.drop_all(bind=auth_engine)
    print("  ✓ Tables dropped")
    
    print("  Creating tables with correct schema...")
    AuthBase.metadata.create_all(bind=auth_engine)
    print("  ✓ Tables created")


def copy_model_data(source_db: Session, target_db: Session, source_model, target_model, batch_size=500):
    """Copy data from source model to target model in batches."""
    model_name = source_model.__tablename__
    target_name = target_model.__tablename__
    print(f"  {model_name} -> {target_name}...", end=" ", flush=True)
    
    try:
        records = source_db.query(source_model).all()
        total = len(records)
        count = 0
        
        # Get target model columns
        target_columns = {c.name for c in target_model.__table__.columns}
        
        for i, record in enumerate(records):
            data = {}
            for column in source_model.__table__.columns:
                source_field = column.name
                value = getattr(record, source_field, None)
                
                if source_field in target_columns:
                    data[source_field] = value
            
            new_record = target_model(**data)
            target_db.add(new_record)
            count += 1
            
            # Commit in batches
            if (i + 1) % batch_size == 0:
                target_db.commit()
        
        # Final commit
        target_db.commit()
        print(f"✓ ({count} records)")
        return count
    except Exception as e:
        target_db.rollback()
        print(f"✗ Error: {str(e)[:80]}")
        return 0


def migrate_all_data():
    """Migrate all data from main DB to auth DB."""
    print("=" * 60)
    print("Data Migration: Main DB -> Auth DB (b2b_ tables)")
    print("=" * 60)
    
    # Step 1: Drop and recreate tables
    drop_and_recreate_tables()
    
    source_db = SessionLocal()
    target_db = AuthSessionLocal()
    
    total_records = 0
    
    try:
        # Phase 1: Base tables (no FKs to other b2b tables)
        print("\n[Phase 1] Base tables...")
        total_records += copy_model_data(source_db, target_db, School, B2BSchool)
        total_records += copy_model_data(source_db, target_db, Therapist, B2BTherapist)
        
        # Phase 2: Users (depends on schools)
        print("\n[Phase 2] Users...")
        total_records += copy_model_data(source_db, target_db, User, B2BUserAuth)
        
        # Phase 3: User-created content (depends on users)
        print("\n[Phase 3] User-created content...")
        total_records += copy_model_data(source_db, target_db, AssessmentTemplate, B2BAssessmentTemplate)
        total_records += copy_model_data(source_db, target_db, Resource, B2BResource)
        total_records += copy_model_data(source_db, target_db, Webinar, B2BWebinar)
        total_records += copy_model_data(source_db, target_db, Class, B2BClass)
        total_records += copy_model_data(source_db, target_db, Activity, B2BActivity)
        total_records += copy_model_data(source_db, target_db, DailyBooster, B2BDailyBooster)
        
        # Phase 4: Students and assessments (depends on classes)
        print("\n[Phase 4] Students and assessments...")
        total_records += copy_model_data(source_db, target_db, Student, B2BStudent)
        total_records += copy_model_data(source_db, target_db, Assessment, B2BAssessment)
        total_records += copy_model_data(source_db, target_db, ActivityAssignment, B2BActivityAssignment)
        
        # Phase 5: Student-related data
        print("\n[Phase 5] Student-related data...")
        total_records += copy_model_data(source_db, target_db, Case, B2BCase)
        total_records += copy_model_data(source_db, target_db, Observation, B2BObservation)
        total_records += copy_model_data(source_db, target_db, RiskAlert, B2BRiskAlert)
        total_records += copy_model_data(source_db, target_db, ConsentRecord, B2BConsentRecord)
        total_records += copy_model_data(source_db, target_db, StudentResponse, B2BStudentResponse)
        total_records += copy_model_data(source_db, target_db, ActivitySubmission, B2BActivitySubmission)
        total_records += copy_model_data(source_db, target_db, TherapistBooking, B2BTherapistBooking)
        
        # Phase 6: Case-related data
        print("\n[Phase 6] Case-related data...")
        total_records += copy_model_data(source_db, target_db, JournalEntry, B2BJournalEntry)
        total_records += copy_model_data(source_db, target_db, SessionNote, B2BSessionNote)
        total_records += copy_model_data(source_db, target_db, Goal, B2BGoal)
        total_records += copy_model_data(source_db, target_db, AIRecommendation, B2BAIRecommendation)
        total_records += copy_model_data(source_db, target_db, CalendarEvent, B2BCalendarEvent)
        
        # Phase 7: Webinar data
        print("\n[Phase 7] Webinar data...")
        total_records += copy_model_data(source_db, target_db, WebinarRegistration, B2BWebinarRegistration)
        total_records += copy_model_data(source_db, target_db, WebinarSchoolRegistration, B2BWebinarSchoolRegistration)
        total_records += copy_model_data(source_db, target_db, StudentWebinarAttendance, B2BStudentWebinarAttendance)
        
        # Phase 8: Comments
        print("\n[Phase 8] Comments...")
        total_records += copy_model_data(source_db, target_db, SubmissionComment, B2BSubmissionComment)
        
        # Phase 9: Engagement data
        print("\n[Phase 9] Engagement data...")
        total_records += copy_model_data(source_db, target_db, StudentAppSession, B2BStudentAppSession)
        total_records += copy_model_data(source_db, target_db, StudentDailyStreak, B2BStudentDailyStreak)
        total_records += copy_model_data(source_db, target_db, StudentStreakSummary, B2BStudentStreakSummary)
        
        print("\n" + "=" * 60)
        print(f"✅ Migration completed! Total records: {total_records}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        source_db.close()
        target_db.close()


if __name__ == "__main__":
    migrate_all_data()
