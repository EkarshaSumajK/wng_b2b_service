#!/usr/bin/env python3
"""
Script to create all b2b_ prefixed tables in the auth database.
Run this script to initialize the auth database schema.

Usage:
    python scripts/create_auth_tables.py
"""
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import create_auth_tables, auth_engine
from app.models.auth.base import AuthBase

def main():
    print("Creating auth database tables (b2b_ prefixed)...")
    print(f"Auth DB URL: {auth_engine.url}")
    
    # Import all models to register them
    from app.models.auth import (
        B2BSchool, B2BUserAuth, B2BStudent, B2BClass, B2BCase, B2BJournalEntry,
        B2BAssessment, B2BAssessmentTemplate, B2BStudentResponse, B2BObservation,
        B2BResource, B2BActivity, B2BRiskAlert, B2BAIRecommendation, B2BConsentRecord,
        B2BGoal, B2BDailyBooster, B2BCalendarEvent, B2BSessionNote, B2BWebinar,
        B2BWebinarSchoolRegistration, B2BWebinarRegistration, B2BTherapist,
        B2BTherapistBooking, B2BActivityAssignment, B2BActivitySubmission,
        B2BSubmissionComment, B2BStudentAppSession, B2BStudentDailyStreak,
        B2BStudentStreakSummary, B2BStudentWebinarAttendance
    )
    
    # List all tables that will be created
    print("\nTables to be created:")
    for table_name in AuthBase.metadata.tables.keys():
        print(f"  - {table_name}")
    
    # Create all tables
    create_auth_tables()
    
    print("\n✅ Auth database tables created successfully!")

if __name__ == "__main__":
    main()
