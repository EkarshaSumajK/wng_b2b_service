"""
Helper functions for working with students stored in b2b_users table.
Students are now stored as User records with role=STUDENT.
Student-specific data is stored in the profile JSON column.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.user import User, UserRole


def get_student_by_id(db: Session, student_id: UUID) -> Optional[User]:
    """Get a student by ID (user_id with role=STUDENT)"""
    return db.query(User).filter(
        User.user_id == student_id,
        User.role == UserRole.STUDENT
    ).first()


def get_students_by_school(db: Session, school_id: UUID, skip: int = 0, limit: int = 300) -> List[User]:
    """Get all students for a school"""
    return db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.STUDENT
    ).offset(skip).limit(limit).all()


def get_students_by_class(db: Session, school_id: UUID, class_id: UUID, skip: int = 0, limit: int = 300) -> List[User]:
    """Get all students for a specific class"""
    # class_id is stored in profile JSON
    students = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.STUDENT
    ).offset(skip).limit(limit).all()
    
    # Filter by class_id from profile
    return [s for s in students if s.profile and s.profile.get('class_id') == str(class_id)]


def get_student_ids_by_school(db: Session, school_id: UUID) -> List[UUID]:
    """Get all student IDs for a school"""
    students = db.query(User.user_id).filter(
        User.school_id == school_id,
        User.role == UserRole.STUDENT
    ).all()
    return [s.user_id for s in students]


def user_to_student_dict(user: User) -> Dict[str, Any]:
    """Convert a User (with role=STUDENT) to student dictionary format"""
    profile = user.profile or {}
    
    # Parse display_name into first_name and last_name
    name_parts = (user.display_name or "").split(" ", 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    return {
        "student_id": user.user_id,
        "school_id": user.school_id,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": user.display_name,
        "email": user.email,
        "pseudonym": profile.get("pseudonym"),
        "roll_number": profile.get("roll_number"),
        "dob": profile.get("dob"),
        "gender": profile.get("gender"),
        "class_id": profile.get("class_id"),
        "grade": profile.get("grade"),
        "section": None,  # Will be populated from class
        "parents_id": profile.get("parents_id"),
        "parent_email": profile.get("parent_email"),
        "parent_phone": profile.get("parent_phone"),
        "risk_level": profile.get("risk_level"),
        "wellbeing_score": profile.get("wellbeing_score"),
        "last_assessment": profile.get("last_assessment"),
        "consent_status": profile.get("consent_status"),
        "notes": profile.get("notes"),
        "additional_info": profile.get("additional_info"),
    }


def get_student_name(user: User) -> str:
    """Get student's full name from User record"""
    return user.display_name or "Unknown"


def get_student_first_name(user: User) -> str:
    """Get student's first name from User record"""
    if user.display_name:
        return user.display_name.split(" ")[0]
    return ""


def get_student_last_name(user: User) -> str:
    """Get student's last name from User record"""
    if user.display_name:
        parts = user.display_name.split(" ", 1)
        return parts[1] if len(parts) > 1 else ""
    return ""
