"""
Teacher Analytics API
Provides analytics data scoped to the classes assigned to a specific teacher.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, desc
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta, date

from app.core.database import get_db
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.models.student import Student, RiskLevel
from app.models.class_model import Class
from app.models.user import User
from app.models.assessment import StudentResponse
from app.models.activity_submission import ActivitySubmission, SubmissionStatus
from app.models.activity_assignment import ActivityAssignment
from app.models.activity_engine import ActivityEngine
from app.models.student_engagement import (
    StudentAppSession, StudentStreakSummary, StudentWebinarAttendance
)
from sqlalchemy.orm import joinedload

logger = get_logger(__name__)
router = APIRouter()


# ============== HELPER FUNCTIONS ==============

def get_date_range(days: int = 30):
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def get_teacher_class_ids(db: Session, teacher_id: UUID) -> List[UUID]:
    """Get all class IDs assigned to a teacher."""
    classes = db.query(Class.class_id).filter(Class.teacher_id == teacher_id).all()
    return [c[0] for c in classes]


def get_teacher_student_ids(db: Session, teacher_id: UUID) -> List[UUID]:
    """Get all student IDs from teacher's classes."""
    class_ids = get_teacher_class_ids(db, teacher_id)
    if not class_ids:
        return []
    students = db.query(Student.student_id).filter(Student.class_id.in_(class_ids)).all()
    return [s[0] for s in students]


# ============== 1. TEACHER OVERVIEW ==============

@router.get("/overview")
async def get_teacher_overview(
    teacher_id: UUID,
    days: int = Query(30, description="Number of days for analytics (7, 30, 90, 365)"),
    db: Session = Depends(get_db)
):
    """
    Get aggregated analytics for all classes assigned to the teacher.
    Returns summary metrics, risk distribution, top performers, and at-risk students.
    """
    # Verify teacher exists
    teacher = db.query(User).filter(User.user_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    start_date, end_date = get_date_range(days)
    start_datetime = datetime.combine(start_date, datetime.min.time())
    
    # Get teacher's classes
    class_ids = get_teacher_class_ids(db, teacher_id)
    if not class_ids:
        return success_response({
            "teacher_id": teacher_id,
            "teacher_name": teacher.display_name or teacher.email,
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "days": days},
            "summary": {"total_students": 0, "total_classes": 0},
            "risk_distribution": {"low": 0, "medium": 0, "high": 0},
            "engagement": {},
            "top_performers": [],
            "at_risk_students": []
        })
    
    # Get student IDs from teacher's classes
    student_ids = get_teacher_student_ids(db, teacher_id)
    
    # Student stats with risk distribution
    student_stats = db.query(
        func.count(Student.student_id).label('total'),
        func.avg(Student.wellbeing_score).label('avg_wellbeing'),
        func.sum(case((Student.risk_level == RiskLevel.LOW, 1), else_=0)).label('low_risk'),
        func.sum(case((Student.risk_level == RiskLevel.MEDIUM, 1), else_=0)).label('medium_risk'),
        func.sum(case((Student.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]), 1), else_=0)).label('high_risk')
    ).filter(Student.class_id.in_(class_ids)).first()
    
    total_students = student_stats.total or 0
    total_classes = len(class_ids)
    
    if not student_ids:
        return success_response({
            "teacher_id": teacher_id,
            "teacher_name": teacher.display_name or teacher.email,
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "days": days},
            "summary": {"total_students": 0, "total_classes": total_classes},
            "risk_distribution": {"low": 0, "medium": 0, "high": 0},
            "engagement": {},
            "top_performers": [],
            "at_risk_students": []
        })
    
    # Streak stats
    streak_stats = db.query(
        func.avg(StudentStreakSummary.current_streak).label('avg_streak')
    ).filter(StudentStreakSummary.student_id.in_(student_ids)).first()
    
    # App sessions
    app_stats = db.query(
        func.count(StudentAppSession.id).label('total_sessions')
    ).filter(
        StudentAppSession.student_id.in_(student_ids),
        StudentAppSession.session_start >= start_datetime
    ).first()
    
    # Activity completion
    activity_stats = db.query(
        func.count(ActivitySubmission.submission_id).label('total'),
        func.sum(case((ActivitySubmission.status.in_([SubmissionStatus.SUBMITTED, SubmissionStatus.VERIFIED]), 1), else_=0)).label('completed')
    ).filter(ActivitySubmission.student_id.in_(student_ids)).first()
    
    # Assessment completion
    assessment_stats = db.query(
        func.count(func.distinct(StudentResponse.assessment_id)).label('completed')
    ).filter(
        StudentResponse.student_id.in_(student_ids),
        StudentResponse.completed_at.isnot(None)
    ).first()
    
    # Top performers
    top_performers_query = db.query(
        Student.student_id,
        Student.first_name,
        Student.last_name,
        Student.wellbeing_score,
        Student.class_id,
        StudentStreakSummary.current_streak
    ).join(
        StudentStreakSummary, Student.student_id == StudentStreakSummary.student_id
    ).filter(
        Student.class_id.in_(class_ids)
    ).order_by(desc(StudentStreakSummary.current_streak)).limit(10).all()
    
    # Get class names
    class_names = {c.class_id: c.name for c in db.query(Class.class_id, Class.name).filter(Class.class_id.in_(class_ids)).all()}
    
    top_performers = [{
        "student_id": t.student_id,
        "student_name": f"{t.first_name} {t.last_name}",
        "class_name": class_names.get(t.class_id),
        "daily_streak": t.current_streak or 0,
        "wellbeing_score": t.wellbeing_score
    } for t in top_performers_query]
    
    # At-risk students
    at_risk_query = db.query(
        Student.student_id,
        Student.first_name,
        Student.last_name,
        Student.wellbeing_score,
        Student.risk_level,
        Student.class_id,
        StudentStreakSummary.last_active_date
    ).outerjoin(
        StudentStreakSummary, Student.student_id == StudentStreakSummary.student_id
    ).filter(
        Student.class_id.in_(class_ids),
        Student.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL])
    ).order_by(Student.wellbeing_score.asc()).limit(10).all()
    
    at_risk_students = [{
        "student_id": a.student_id,
        "student_name": f"{a.first_name} {a.last_name}",
        "class_name": class_names.get(a.class_id),
        "wellbeing_score": a.wellbeing_score,
        "risk_level": a.risk_level.value.lower() if a.risk_level else "low",
        "last_active": a.last_active_date.isoformat() + "T00:00:00Z" if a.last_active_date else None
    } for a in at_risk_query]
    
    activity_completion = round((activity_stats.completed or 0) / (activity_stats.total or 1) * 100, 1)
    
    return success_response({
        "teacher_id": teacher_id,
        "teacher_name": teacher.display_name or teacher.email,
        "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "days": days},
        "summary": {
            "total_students": total_students,
            "total_classes": total_classes,
            "avg_wellbeing_score": round(student_stats.avg_wellbeing, 1) if student_stats.avg_wellbeing else None,
            "avg_activity_completion": activity_completion,
            "avg_daily_streak": round(streak_stats.avg_streak, 1) if streak_stats and streak_stats.avg_streak else 0,
            "total_app_openings": app_stats.total_sessions or 0
        },
        "risk_distribution": {
            "low": student_stats.low_risk or 0,
            "medium": student_stats.medium_risk or 0,
            "high": student_stats.high_risk or 0
        },
        "engagement": {
            "total_app_openings": app_stats.total_sessions or 0,
            "total_assessments_completed": assessment_stats.completed or 0,
            "total_activities_completed": activity_stats.completed or 0
        },
        "top_performers": top_performers,
        "at_risk_students": at_risk_students
    })



# ============== 2. TEACHER'S CLASSES ==============

@router.get("/classes")
async def get_teacher_classes(
    teacher_id: UUID,
    search: Optional[str] = Query(None, description="Search by class name"),
    days: int = Query(30, description="Number of days for analytics"),
    db: Session = Depends(get_db)
):
    """
    Get list of classes assigned to the teacher with analytics metrics.
    """
    # Verify teacher exists
    teacher = db.query(User).filter(User.user_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    start_date, end_date = get_date_range(days)
    
    # Get teacher's classes
    classes_query = db.query(Class).filter(Class.teacher_id == teacher_id)
    if search:
        classes_query = classes_query.filter(Class.name.ilike(f"%{search}%"))
    
    classes = classes_query.all()
    
    if not classes:
        return success_response({
            "total_classes": 0,
            "classes": []
        })
    
    class_data = []
    for cls in classes:
        # Get students in this class
        students = db.query(Student).filter(Student.class_id == cls.class_id).all()
        student_ids = [s.student_id for s in students]
        total_students = len(students)
        
        if not student_ids:
            class_data.append({
                "class_id": cls.class_id,
                "name": cls.name,
                "grade": cls.grade,
                "section": cls.section,
                "total_students": 0,
                "metrics": {"avg_wellbeing": None, "assessment_completion": 0, "activity_completion": 0, "avg_daily_streak": 0},
                "risk_distribution": {"low": 0, "medium": 0, "high": 0},
                "at_risk_count": 0
            })
            continue
        
        # Student stats
        student_stats = db.query(
            func.avg(Student.wellbeing_score).label('avg_wellbeing'),
            func.sum(case((Student.risk_level == RiskLevel.LOW, 1), else_=0)).label('low_risk'),
            func.sum(case((Student.risk_level == RiskLevel.MEDIUM, 1), else_=0)).label('medium_risk'),
            func.sum(case((Student.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]), 1), else_=0)).label('high_risk')
        ).filter(Student.class_id == cls.class_id).first()
        
        # Streak stats
        streak_stats = db.query(
            func.avg(StudentStreakSummary.current_streak).label('avg_streak')
        ).filter(StudentStreakSummary.student_id.in_(student_ids)).first()
        
        # Activity completion
        activity_stats = db.query(
            func.count(ActivitySubmission.submission_id).label('total'),
            func.sum(case((ActivitySubmission.status.in_([SubmissionStatus.SUBMITTED, SubmissionStatus.VERIFIED]), 1), else_=0)).label('completed')
        ).filter(ActivitySubmission.student_id.in_(student_ids)).first()
        
        # Assessment completion
        assessment_total = db.query(func.count(func.distinct(StudentResponse.assessment_id))).filter(
            StudentResponse.student_id.in_(student_ids)
        ).scalar() or 0
        
        assessment_completed = db.query(func.count(func.distinct(StudentResponse.assessment_id))).filter(
            StudentResponse.student_id.in_(student_ids),
            StudentResponse.completed_at.isnot(None)
        ).scalar() or 0
        
        activity_completion = round((activity_stats.completed or 0) / (activity_stats.total or 1) * 100, 1)
        assessment_completion = round(assessment_completed / (assessment_total or 1) * 100, 1)
        
        class_data.append({
            "class_id": cls.class_id,
            "name": cls.name,
            "grade": cls.grade,
            "section": cls.section,
            "total_students": total_students,
            "metrics": {
                "avg_wellbeing": round(student_stats.avg_wellbeing, 1) if student_stats.avg_wellbeing else None,
                "assessment_completion": assessment_completion,
                "activity_completion": activity_completion,
                "avg_daily_streak": round(streak_stats.avg_streak, 1) if streak_stats and streak_stats.avg_streak else 0
            },
            "risk_distribution": {
                "low": student_stats.low_risk or 0,
                "medium": student_stats.medium_risk or 0,
                "high": student_stats.high_risk or 0
            },
            "at_risk_count": (student_stats.high_risk or 0)
        })
    
    return success_response({
        "total_classes": len(class_data),
        "classes": class_data
    })



# ============== 3. CLASS DETAILS ==============

@router.get("/classes/{class_id}")
async def get_class_details(
    class_id: UUID,
    days: int = Query(30, description="Number of days for analytics"),
    db: Session = Depends(get_db)
):
    """
    Get detailed analytics for a specific class including student list.
    """
    cls = db.query(Class).filter(Class.class_id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    
    start_date, end_date = get_date_range(days)
    
    # Get students in this class
    students = db.query(Student).filter(Student.class_id == class_id).all()
    student_ids = [s.student_id for s in students]
    total_students = len(students)
    
    if not student_ids:
        return success_response({
            "class_id": cls.class_id,
            "name": cls.name,
            "grade": cls.grade,
            "section": cls.section,
            "total_students": 0,
            "metrics": {"avg_wellbeing": None, "assessment_completion": 0, "activity_completion": 0, "avg_daily_streak": 0},
            "risk_distribution": {"low": 0, "medium": 0, "high": 0},
            "at_risk_count": 0,
            "students": []
        })
    
    # Student stats
    student_stats = db.query(
        func.avg(Student.wellbeing_score).label('avg_wellbeing'),
        func.sum(case((Student.risk_level == RiskLevel.LOW, 1), else_=0)).label('low_risk'),
        func.sum(case((Student.risk_level == RiskLevel.MEDIUM, 1), else_=0)).label('medium_risk'),
        func.sum(case((Student.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]), 1), else_=0)).label('high_risk')
    ).filter(Student.class_id == class_id).first()
    
    # Streak stats
    streak_stats = db.query(
        func.avg(StudentStreakSummary.current_streak).label('avg_streak')
    ).filter(StudentStreakSummary.student_id.in_(student_ids)).first()
    
    # Activity completion
    activity_stats = db.query(
        func.count(ActivitySubmission.submission_id).label('total'),
        func.sum(case((ActivitySubmission.status.in_([SubmissionStatus.SUBMITTED, SubmissionStatus.VERIFIED]), 1), else_=0)).label('completed')
    ).filter(ActivitySubmission.student_id.in_(student_ids)).first()
    
    # Assessment stats
    assessment_completed = db.query(func.count(func.distinct(StudentResponse.assessment_id))).filter(
        StudentResponse.student_id.in_(student_ids),
        StudentResponse.completed_at.isnot(None)
    ).scalar() or 0
    
    assessment_total = db.query(func.count(func.distinct(StudentResponse.assessment_id))).filter(
        StudentResponse.student_id.in_(student_ids)
    ).scalar() or 0
    
    activity_completion = round((activity_stats.completed or 0) / (activity_stats.total or 1) * 100, 1)
    assessment_completion = round(assessment_completed / (assessment_total or 1) * 100, 1)
    
    # Get streak data for all students
    streak_map = {s.student_id: s for s in db.query(StudentStreakSummary).filter(
        StudentStreakSummary.student_id.in_(student_ids)
    ).all()}
    
    # Get assessment counts per student
    assessment_counts = dict(db.query(
        StudentResponse.student_id,
        func.count(func.distinct(StudentResponse.assessment_id))
    ).filter(
        StudentResponse.student_id.in_(student_ids),
        StudentResponse.completed_at.isnot(None)
    ).group_by(StudentResponse.student_id).all())
    
    # Get activity counts per student
    activity_counts = dict(db.query(
        ActivitySubmission.student_id,
        func.count(ActivitySubmission.submission_id)
    ).filter(
        ActivitySubmission.student_id.in_(student_ids),
        ActivitySubmission.status.in_([SubmissionStatus.SUBMITTED, SubmissionStatus.VERIFIED])
    ).group_by(ActivitySubmission.student_id).all())
    
    # Build student list
    student_list = []
    for s in students:
        streak = streak_map.get(s.student_id)
        student_list.append({
            "student_id": s.student_id,
            "name": f"{s.first_name} {s.last_name}",
            "wellbeing_score": s.wellbeing_score,
            "risk_level": s.risk_level.value.lower() if s.risk_level else "low",
            "daily_streak": streak.current_streak if streak else 0,
            "max_streak": streak.max_streak if streak else 0,
            "last_active": streak.last_active_date.isoformat() + "T00:00:00Z" if streak and streak.last_active_date else None,
            "assessments_completed": assessment_counts.get(s.student_id, 0),
            "activities_completed": activity_counts.get(s.student_id, 0)
        })
    
    return success_response({
        "class_id": cls.class_id,
        "name": cls.name,
        "grade": cls.grade,
        "section": cls.section,
        "total_students": total_students,
        "metrics": {
            "avg_wellbeing": round(student_stats.avg_wellbeing, 1) if student_stats.avg_wellbeing else None,
            "assessment_completion": assessment_completion,
            "activity_completion": activity_completion,
            "avg_daily_streak": round(streak_stats.avg_streak, 1) if streak_stats and streak_stats.avg_streak else 0
        },
        "risk_distribution": {
            "low": student_stats.low_risk or 0,
            "medium": student_stats.medium_risk or 0,
            "high": student_stats.high_risk or 0
        },
        "at_risk_count": student_stats.high_risk or 0,
        "students": student_list
    })



# ============== 4. TEACHER'S STUDENTS ==============

@router.get("/students")
async def get_teacher_students(
    teacher_id: UUID,
    class_id: Optional[UUID] = Query(None, description="Filter by specific class"),
    search: Optional[str] = Query(None, description="Search by student name"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level: low, medium, high"),
    days: int = Query(30, description="Number of days for analytics"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of all students from the teacher's classes.
    """
    # Verify teacher exists
    teacher = db.query(User).filter(User.user_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    start_date, end_date = get_date_range(days)
    
    # Get teacher's classes
    class_ids = get_teacher_class_ids(db, teacher_id)
    if not class_ids:
        return success_response({
            "total_students": 0,
            "page": page,
            "limit": limit,
            "total_pages": 0,
            "students": []
        })
    
    # Build student query
    students_query = db.query(Student).filter(Student.class_id.in_(class_ids))
    
    # Apply filters
    if class_id:
        if class_id not in class_ids:
            raise HTTPException(status_code=403, detail="Access denied. Teacher is not assigned to this class.")
        students_query = students_query.filter(Student.class_id == class_id)
    
    if search:
        students_query = students_query.filter(
            func.concat(Student.first_name, ' ', Student.last_name).ilike(f"%{search}%")
        )
    
    if risk_level:
        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": [RiskLevel.HIGH, RiskLevel.CRITICAL]
        }
        if risk_level.lower() == "high":
            students_query = students_query.filter(Student.risk_level.in_(risk_map["high"]))
        elif risk_level.lower() in risk_map:
            students_query = students_query.filter(Student.risk_level == risk_map[risk_level.lower()])
    
    # Get total count
    total_students = students_query.count()
    total_pages = (total_students + limit - 1) // limit
    
    # Apply pagination
    offset = (page - 1) * limit
    students = students_query.offset(offset).limit(limit).all()
    
    if not students:
        return success_response({
            "total_students": total_students,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "students": []
        })
    
    student_ids = [s.student_id for s in students]
    
    # Get class names
    class_names = {c.class_id: c.name for c in db.query(Class.class_id, Class.name).filter(Class.class_id.in_(class_ids)).all()}
    
    # Get streak data
    streak_map = {s.student_id: s for s in db.query(StudentStreakSummary).filter(
        StudentStreakSummary.student_id.in_(student_ids)
    ).all()}
    
    # Get assessment counts
    assessment_counts = dict(db.query(
        StudentResponse.student_id,
        func.count(func.distinct(StudentResponse.assessment_id))
    ).filter(
        StudentResponse.student_id.in_(student_ids),
        StudentResponse.completed_at.isnot(None)
    ).group_by(StudentResponse.student_id).all())
    
    # Get activity counts
    activity_counts = dict(db.query(
        ActivitySubmission.student_id,
        func.count(ActivitySubmission.submission_id)
    ).filter(
        ActivitySubmission.student_id.in_(student_ids),
        ActivitySubmission.status.in_([SubmissionStatus.SUBMITTED, SubmissionStatus.VERIFIED])
    ).group_by(ActivitySubmission.student_id).all())
    
    # Build student list
    student_list = []
    for s in students:
        streak = streak_map.get(s.student_id)
        student_list.append({
            "student_id": s.student_id,
            "name": f"{s.first_name} {s.last_name}",
            "class_id": s.class_id,
            "class_name": class_names.get(s.class_id),
            "wellbeing_score": s.wellbeing_score,
            "risk_level": s.risk_level.value.lower() if s.risk_level else "low",
            "daily_streak": streak.current_streak if streak else 0,
            "max_streak": streak.max_streak if streak else 0,
            "last_active": streak.last_active_date.isoformat() + "T00:00:00Z" if streak and streak.last_active_date else None,
            "assessments_completed": assessment_counts.get(s.student_id, 0),
            "activities_completed": activity_counts.get(s.student_id, 0)
        })
    
    return success_response({
        "total_students": total_students,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "students": student_list
    })



# ============== 5. STUDENT ACTIVITIES ==============

@router.get("/students/{student_id}/activities")
async def get_student_activity_history(
    student_id: UUID,
    status: Optional[str] = Query(None, description="Filter by status: PENDING, SUBMITTED, VERIFIED, REJECTED"),
    days: Optional[int] = Query(None, description="Filter to last N days"),
    db: Session = Depends(get_db)
):
    """
    Get activity history for a specific student.
    Teacher must have access to the student's class.
    """
    # Verify student exists
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Status breakdown (always get full stats)
    status_stats = db.query(
        ActivitySubmission.status,
        func.count(ActivitySubmission.submission_id).label('count')
    ).filter(ActivitySubmission.student_id == student_id).group_by(ActivitySubmission.status).all()
    
    status_breakdown = {"pending": 0, "submitted": 0, "verified": 0, "rejected": 0}
    for row in status_stats:
        status_breakdown[row.status.value.lower()] = row.count
    
    # Filtered query
    query = db.query(ActivitySubmission).options(
        joinedload(ActivitySubmission.assignment)
    ).filter(ActivitySubmission.student_id == student_id)
    
    if status:
        try:
            query = query.filter(ActivitySubmission.status == SubmissionStatus(status.upper()))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    if days:
        query = query.filter(ActivitySubmission.created_at >= datetime.utcnow() - timedelta(days=days))
    
    submissions = query.order_by(ActivitySubmission.created_at.desc()).all()
    
    # Batch fetch activities
    activity_ids = [sub.assignment.activity_id for sub in submissions if sub.assignment]
    activities_map = {}
    if activity_ids:
        activities_data = db.query(ActivityEngine).filter(ActivityEngine.activity_id.in_(activity_ids)).all()
        activities_map = {str(a.activity_id): a for a in activities_data}
    
    activities = []
    for sub in submissions:
        activity = activities_map.get(str(sub.assignment.activity_id)) if sub.assignment else None
        activities.append({
            "submission_id": sub.submission_id,
            "activity_id": activity.activity_id if activity else (sub.assignment.activity_id if sub.assignment else None),
            "activity_title": activity.title if activity else None,
            "activity_type": activity.activity_type if activity else None,
            "assigned_at": sub.assignment.created_at if sub.assignment else None,
            "due_date": sub.assignment.due_date if sub.assignment else None,
            "submitted_at": sub.submitted_at,
            "status": sub.status.value,
            "feedback": sub.feedback,
            "file_url": sub.file_url
        })
    
    return success_response({
        "student_id": student_id,
        "student_name": f"{student.first_name} {student.last_name}",
        "total_activities": sum(status_breakdown.values()),
        "status_breakdown": status_breakdown,
        "activities": activities
    })


# ============== 6. STUDENT ASSESSMENTS ==============

@router.get("/students/{student_id}/assessments")
async def get_student_assessment_history(
    student_id: UUID,
    include_responses: bool = Query(False, description="Include individual question responses"),
    days: Optional[int] = Query(None, description="Filter to last N days"),
    db: Session = Depends(get_db)
):
    """
    Get assessment history for a specific student.
    """
    from app.models.assessment import Assessment, AssessmentTemplate
    
    # Verify student exists
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get responses with eager loading
    query = db.query(StudentResponse).options(
        joinedload(StudentResponse.assessment).joinedload(Assessment.template)
    ).filter(StudentResponse.student_id == student_id, StudentResponse.completed_at.isnot(None))
    
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(StudentResponse.completed_at >= cutoff)
    
    responses = query.order_by(StudentResponse.completed_at.desc()).all()
    
    # Group by assessment
    assessment_map = {}
    for r in responses:
        a_id = r.assessment_id
        if a_id not in assessment_map:
            template = r.assessment.template
            assessment_map[a_id] = {
                "assessment_id": a_id,
                "template_id": template.template_id,
                "template_name": template.name,
                "category": template.category,
                "completed_at": r.completed_at,
                "total_score": 0.0,
                "max_score": len(template.questions) * 5,
                "total_questions": len(template.questions),
                "questions_answered": 0,
                "responses": [] if include_responses else None
            }
        
        assessment_map[a_id]["total_score"] += r.score or 0
        assessment_map[a_id]["questions_answered"] += 1
        
        if include_responses:
            assessment_map[a_id]["responses"].append({
                "question_id": r.question_id,
                "question_text": r.question_text,
                "answer_value": r.answer,
                "score": r.score
            })
    
    # Add risk level
    assessments = []
    for a in assessment_map.values():
        ratio = a["total_score"] / a["max_score"] if a["max_score"] > 0 else 0
        a["risk_level"] = "low" if ratio < 0.33 else ("medium" if ratio < 0.66 else "high")
        assessments.append(a)
    
    return success_response({
        "student_id": student_id,
        "student_name": f"{student.first_name} {student.last_name}",
        "total_assessments": len(assessments),
        "assessments": assessments
    })


# ============== 7. ASSESSMENT MONITORING ==============

@router.get("/assessments/{assessment_id}/monitoring")
async def get_assessment_monitoring(
    assessment_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Monitor assessment completion and response consistency for teacher's class.
    
    Returns:
    - Expected vs actual responses per student
    - Students with incomplete responses
    - Students who haven't started
    - Response consistency check
    """
    from app.models.assessment import Assessment, AssessmentTemplate
    
    assessment = (
        db.query(Assessment)
        .options(joinedload(Assessment.template), joinedload(Assessment.class_obj))
        .filter(Assessment.assessment_id == assessment_id)
        .first()
    )
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    template = assessment.template
    total_questions = len(template.questions)
    question_ids = {q['question_id'] for q in template.questions}
    
    # Get all students who should take this assessment
    expected_students = []
    if assessment.class_id:
        students_query = db.query(Student).filter(Student.class_id == assessment.class_id)
        # Exclude students in exclusion list
        if assessment.excluded_students:
            students_query = students_query.filter(~Student.student_id.in_(assessment.excluded_students))
        expected_students = students_query.all()
    
    expected_student_ids = {s.student_id for s in expected_students}
    
    # Get all responses for this assessment
    responses = (
        db.query(StudentResponse)
        .filter(StudentResponse.assessment_id == assessment_id)
        .all()
    )
    
    # Group responses by student
    student_responses = {}
    for response in responses:
        if response.student_id not in student_responses:
            student_responses[response.student_id] = {
                "responses": [],
                "question_ids": set(),
                "completed_at": response.completed_at
            }
        student_responses[response.student_id]["responses"].append(response)
        student_responses[response.student_id]["question_ids"].add(response.question_id)
    
    # Analyze each student
    completed_students = []
    incomplete_students = []
    not_started_students = []
    
    for student in expected_students:
        student_info = {
            "student_id": student.student_id,
            "student_name": f"{student.first_name} {student.last_name}"
        }
        
        if student.student_id not in student_responses:
            not_started_students.append(student_info)
        else:
            data = student_responses[student.student_id]
            answered_count = len(data["question_ids"])
            missing_questions = question_ids - data["question_ids"]
            extra_questions = data["question_ids"] - question_ids
            
            student_detail = {
                **student_info,
                "expected_questions": total_questions,
                "answered_questions": answered_count,
                "missing_questions": list(missing_questions),
                "extra_questions": list(extra_questions),
                "completed_at": data["completed_at"],
                "total_score": sum(r.score or 0 for r in data["responses"])
            }
            
            if answered_count == total_questions and not extra_questions:
                completed_students.append(student_detail)
            else:
                incomplete_students.append(student_detail)
    
    # Students who responded but weren't expected (not in class)
    unexpected_students = []
    for student_id in student_responses.keys():
        if student_id not in expected_student_ids:
            student = db.query(Student).filter(Student.student_id == student_id).first()
            if student:
                data = student_responses[student_id]
                unexpected_students.append({
                    "student_id": student_id,
                    "student_name": f"{student.first_name} {student.last_name}",
                    "answered_questions": len(data["question_ids"]),
                    "completed_at": data["completed_at"]
                })
    
    return success_response({
        "assessment_id": assessment_id,
        "template_name": template.name,
        "title": assessment.title,
        "class_name": assessment.class_obj.name if assessment.class_obj else None,
        "total_questions": total_questions,
        "question_ids": list(question_ids),
        "summary": {
            "expected_students": len(expected_students),
            "completed": len(completed_students),
            "incomplete": len(incomplete_students),
            "not_started": len(not_started_students),
            "unexpected_responses": len(unexpected_students),
            "completion_rate": round(len(completed_students) / len(expected_students) * 100, 1) if expected_students else 0
        },
        "completed_students": completed_students,
        "incomplete_students": incomplete_students,
        "not_started_students": not_started_students,
        "unexpected_students": unexpected_students
    })


@router.get("/assessments/{assessment_id}/question-breakdown")
async def get_assessment_question_breakdown(
    assessment_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get detailed question-by-question breakdown for an assessment.
    Shows which questions each student answered and their scores.
    """
    from app.models.assessment import Assessment, AssessmentTemplate
    import statistics
    
    def calculate_statistics(values):
        if not values:
            return {}
        return {
            "mean": round(statistics.mean(values), 2),
            "min": min(values),
            "max": max(values)
        }
    
    assessment = (
        db.query(Assessment)
        .options(joinedload(Assessment.template))
        .filter(Assessment.assessment_id == assessment_id)
        .first()
    )
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    template = assessment.template
    questions = template.questions
    
    # Get all responses
    responses = (
        db.query(StudentResponse)
        .filter(StudentResponse.assessment_id == assessment_id)
        .all()
    )
    
    # Build question-centric view
    question_data = {}
    for q in questions:
        q_id = q['question_id']
        question_data[q_id] = {
            "question_id": q_id,
            "question_text": q['question_text'],
            "question_type": q.get('question_type'),
            "responses": [],
            "response_count": 0,
            "scores": []
        }
    
    # Map responses to questions
    for response in responses:
        q_id = response.question_id
        if q_id in question_data:
            student = db.query(Student).filter(Student.student_id == response.student_id).first()
            question_data[q_id]["responses"].append({
                "student_id": response.student_id,
                "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown",
                "answer": response.answer,
                "score": response.score
            })
            question_data[q_id]["response_count"] += 1
            if response.score is not None:
                question_data[q_id]["scores"].append(response.score)
    
    # Calculate stats per question
    question_breakdown = []
    for q_id, data in question_data.items():
        stats = calculate_statistics(data["scores"]) if data["scores"] else {}
        question_breakdown.append({
            "question_id": data["question_id"],
            "question_text": data["question_text"],
            "question_type": data["question_type"],
            "response_count": data["response_count"],
            "average_score": stats.get("mean"),
            "min_score": stats.get("min"),
            "max_score": stats.get("max"),
            "responses": data["responses"]
        })
    
    return success_response({
        "assessment_id": assessment_id,
        "template_name": template.name,
        "title": assessment.title,
        "total_questions": len(questions),
        "question_breakdown": question_breakdown
    })


# ============== 8. TEACHER TRENDS ==============

@router.get("/trends")
async def get_teacher_trends(
    teacher_id: UUID,
    days: int = Query(30, description="Number of days for analytics"),
    db: Session = Depends(get_db)
):
    """Daily completion rates for assessments, activities, and webinars for teacher's classes."""
    start_date, end_date = get_date_range(days)
    
    # Get teacher's student IDs
    student_ids = get_teacher_student_ids(db, teacher_id)
    
    if not student_ids:
        return success_response({"trends": []})

    # Initialize daily map
    trends_map = {}
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.isoformat()
        trends_map[date_str] = {
            "date": date_str,
            "assessments": 0,
            "activities": 0,
            "webinars": 0
        }
        current_date += timedelta(days=1)
    
    # Assessments (by completed_at)
    assessment_data = db.query(
        func.date(StudentResponse.completed_at).label('date'),
        func.count(func.distinct(StudentResponse.student_id)).label('count')
    ).filter(
        StudentResponse.student_id.in_(student_ids),
        StudentResponse.completed_at >= datetime.combine(start_date, datetime.min.time())
    ).group_by(func.date(StudentResponse.completed_at)).all()
    
    # Activities (by submitted_at)
    activity_data = db.query(
        func.date(ActivitySubmission.submitted_at).label('date'),
        func.count(ActivitySubmission.submission_id).label('count')
    ).filter(
        ActivitySubmission.student_id.in_(student_ids),
        ActivitySubmission.submitted_at >= datetime.combine(start_date, datetime.min.time())
    ).group_by(func.date(ActivitySubmission.submitted_at)).all()

    # Webinars (by created_at of attendance record)
    webinar_data = db.query(
        func.date(StudentWebinarAttendance.created_at).label('date'),
        func.count(StudentWebinarAttendance.id).label('count')
    ).filter(
        StudentWebinarAttendance.student_id.in_(student_ids),
        StudentWebinarAttendance.created_at >= datetime.combine(start_date, datetime.min.time()),
        StudentWebinarAttendance.attended == True
    ).group_by(func.date(StudentWebinarAttendance.created_at)).all()
    
    total_students = len(student_ids) or 1

    def get_date_str(d):
        if isinstance(d, str):
            return d
        if hasattr(d, 'isoformat'):
            return d.isoformat()
        return str(d)

    for row in assessment_data:
        d_str = get_date_str(row.date)
        if d_str in trends_map:
            trends_map[d_str]["assessments"] = min(100, round((row.count / total_students) * 100, 1))
            
    for row in activity_data:
        d_str = get_date_str(row.date)
        if d_str in trends_map:
            trends_map[d_str]["activities"] = min(100, round((row.count / total_students) * 100, 1))
            
    for row in webinar_data:
        d_str = get_date_str(row.date)
        if d_str in trends_map:
            trends_map[d_str]["webinars"] = min(100, round((row.count / total_students) * 100, 1))
            
    return success_response({"trends": list(trends_map.values())})


# ============== 9. TEACHER ASSESSMENTS LIST ==============

@router.get("/assessments")
async def get_teacher_assessments(
    teacher_id: UUID,
    class_id: Optional[UUID] = Query(None, description="Filter by specific class"),
    days: int = Query(30, description="Number of days for analytics"),
    db: Session = Depends(get_db)
):
    """List of assessments with completion stats for teacher's classes."""
    from app.models.assessment import Assessment, AssessmentTemplate
    
    start_date, end_date = get_date_range(days)
    class_ids = get_teacher_class_ids(db, teacher_id)
    
    if not class_ids:
        return success_response({"assessments": []})
    
    # Filter by specific class if provided
    if class_id:
        if class_id not in class_ids:
            raise HTTPException(status_code=403, detail="Access denied. Teacher is not assigned to this class.")
        class_ids = [class_id]
    
    # Get assessment templates with completion stats
    query = db.query(
        AssessmentTemplate.template_id,
        AssessmentTemplate.name,
        AssessmentTemplate.category,
        func.count(func.distinct(StudentResponse.student_id)).label('submitted_count'),
        func.avg(StudentResponse.score).label('avg_score')
    ).join(Assessment, Assessment.template_id == AssessmentTemplate.template_id
    ).join(StudentResponse, and_(
        StudentResponse.assessment_id == Assessment.assessment_id,
        StudentResponse.completed_at >= datetime.combine(start_date, datetime.min.time())
    )).filter(Assessment.class_id.in_(class_ids)
    ).group_by(AssessmentTemplate.template_id, AssessmentTemplate.name, AssessmentTemplate.category).all()

    # Get total students in teacher's classes
    student_count = db.query(func.count(Student.student_id)).filter(
        Student.class_id.in_(class_ids)
    ).scalar() or 1
    
    results = []
    for row in query:
        results.append({
            "id": row.template_id,
            "title": row.name,
            "category": row.category,
            "studentsSubmitted": row.submitted_count,
            "totalStudentsAssigned": student_count,
            "submissionRate": round((row.submitted_count / student_count) * 100, 1) if student_count > 0 else 0,
            "avgScore": round(float(row.avg_score), 1) if row.avg_score else 0
        })
        
    return success_response({"assessments": results})


# ============== 10. TEACHER ACTIVITIES LIST ==============

@router.get("/activities")
async def get_teacher_activities(
    teacher_id: UUID,
    class_id: Optional[UUID] = Query(None, description="Filter by specific class"),
    days: int = Query(30, description="Number of days for analytics"),
    db: Session = Depends(get_db)
):
    """List of activities with completion stats for teacher's classes."""
    from sqlalchemy import text
    
    start_date, end_date = get_date_range(days)
    class_ids = get_teacher_class_ids(db, teacher_id)
    
    if not class_ids:
        return success_response({"activities": []})
    
    if class_id:
        if class_id not in class_ids:
            raise HTTPException(status_code=403, detail="Access denied. Teacher is not assigned to this class.")
        class_ids = [class_id]

    # Get total students
    student_count = db.query(func.count(Student.student_id)).filter(
        Student.class_id.in_(class_ids)
    ).scalar() or 1
    
    # Query starting from assignments (same as monitoring page) with LEFT JOIN to activities
    start_datetime = datetime.combine(start_date, datetime.min.time())
    class_ids_str = ', '.join([f"'{str(cid)}'" for cid in class_ids])
    
    query = text(f"""
        SELECT 
            aa.activity_id,
            COALESCE(a.title, 'Unknown Activity') as title,
            COALESCE(a.activity_type, 'Activity') as type,
            COUNT(DISTINCT CASE 
                WHEN s.status IN ('SUBMITTED', 'VERIFIED') 
                AND s.submitted_at >= :start_date 
                THEN s.student_id 
            END) as completed_count
        FROM b2b_activity_assignments aa
        LEFT JOIN activities a ON a.activity_id = aa.activity_id
        LEFT JOIN b2b_activity_submissions s ON s.assignment_id = aa.assignment_id
        WHERE aa.class_id IN ({class_ids_str})
        AND aa.status = 'ACTIVE'
        GROUP BY aa.activity_id, a.title, a.activity_type
    """)
    
    result = db.execute(query, {"start_date": start_datetime})
    
    results = []
    for row in result:
        completed = row.completed_count or 0
        results.append({
            "id": row.activity_id,
            "title": row.title or 'Unknown Activity',
            "type": row.type or 'Activity',
            "studentsCompleted": completed,
            "totalStudentsAssigned": student_count,
            "completionRate": round((completed / student_count) * 100, 1) if student_count > 0 else 0
        })
    
    return success_response({"activities": results})


# ============== 11. TEACHER WEBINARS LIST ==============

@router.get("/webinars")
async def get_teacher_webinars(
    teacher_id: UUID,
    class_id: Optional[UUID] = Query(None, description="Filter by specific class"),
    days: int = Query(30, description="Number of days for analytics"),
    db: Session = Depends(get_db)
):
    """List of webinars with attendance stats for teacher's classes."""
    from app.models.webinar import Webinar, WebinarSchoolRegistration
    
    start_date, end_date = get_date_range(days)
    start_datetime = datetime.combine(start_date, datetime.min.time())
    
    class_ids = get_teacher_class_ids(db, teacher_id)
    if not class_ids:
        return success_response({"webinars": []})
    
    if class_id:
        if class_id not in class_ids:
            raise HTTPException(status_code=403, detail="Access denied. Teacher is not assigned to this class.")
        class_ids = [class_id]
    
    # Get school_id from teacher's classes
    school_id = db.query(Class.school_id).filter(Class.class_id.in_(class_ids)).first()
    if not school_id:
        return success_response({"webinars": []})
    school_id = school_id[0]
    
    # Get webinars registered for this school
    registrations = db.query(WebinarSchoolRegistration).filter(
        WebinarSchoolRegistration.school_id == school_id
    ).all()
    
    if not registrations:
        return success_response({"webinars": []})

    webinar_ids = [reg.webinar_id for reg in registrations]
    webinars = db.query(Webinar).filter(
        Webinar.webinar_id.in_(webinar_ids)
    ).order_by(Webinar.date.desc()).all()
    
    if not webinars:
        return success_response({"webinars": []})
    
    results = []
    for w in webinars:
        # Count students in teacher's classes
        total_invited = db.query(func.count(Student.student_id)).filter(
            Student.class_id.in_(class_ids)
        ).scalar() or 0
        
        # Get attendance count
        attended = db.query(func.count(StudentWebinarAttendance.id)).join(
            Student, StudentWebinarAttendance.student_id == Student.student_id
        ).filter(
            StudentWebinarAttendance.webinar_id == w.webinar_id,
            StudentWebinarAttendance.attended == True,
            Student.class_id.in_(class_ids)
        ).scalar() or 0
        
        results.append({
            "id": w.webinar_id,
            "title": w.title,
            "date": w.date.isoformat() if w.date else None,
            "studentsAttended": attended,
            "totalStudentsInvited": total_invited,
            "attendanceRate": round((attended / total_invited) * 100, 1) if total_invited > 0 else 0
        })
    
    return success_response({"webinars": results})


# ============== 12. TEACHER ASSESSMENT DETAILS ==============

@router.get("/assessments/{template_id}/details")
async def get_teacher_assessment_details(
    template_id: UUID,
    teacher_id: UUID,
    days: int = Query(30, description="Number of days for analytics"),
    db: Session = Depends(get_db)
):
    """Detailed view of a specific assessment for teacher's classes."""
    from app.models.assessment import Assessment, AssessmentTemplate
    
    start_date, end_date = get_date_range(days)
    class_ids = get_teacher_class_ids(db, teacher_id)
    
    if not class_ids:
        raise HTTPException(status_code=403, detail="Teacher has no assigned classes")
    
    template = db.query(AssessmentTemplate).filter(AssessmentTemplate.template_id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Get assessments for teacher's classes
    assessments = db.query(Assessment).filter(
        Assessment.template_id == template_id,
        Assessment.class_id.in_(class_ids)
    ).all()
    
    # Get students from teacher's classes
    students = db.query(Student).filter(Student.class_id.in_(class_ids)).all()
    student_map = {s.student_id: s for s in students}
    
    # Get class names
    classes = db.query(Class).filter(Class.class_id.in_(class_ids)).all()
    class_map = {c.class_id: c.name for c in classes}

    # Get responses
    responses = db.query(StudentResponse).join(Assessment).filter(
        Assessment.template_id == template_id,
        Assessment.class_id.in_(class_ids),
        StudentResponse.completed_at >= datetime.combine(start_date, datetime.min.time())
    ).all()
    
    response_map = {r.student_id: r for r in responses}
    max_score = sum([q.get('points', 0) for q in (template.questions or [])]) or 100
    
    submissions = []
    total_score = 0
    pass_count = 0
    class_stats = {}
    
    for s in students:
        resp = response_map.get(s.student_id)
        status = "submitted" if resp else "pending"
        score = resp.score if resp else 0
        c_name = class_map.get(s.class_id, "Unknown")
        
        if s.class_id not in class_stats:
            class_stats[s.class_id] = {"className": c_name, "total": 0, "submitted": 0, "total_score": 0}
        class_stats[s.class_id]["total"] += 1
        
        if resp:
            total_score += score
            if (score / max_score) >= 0.6:
                pass_count += 1
            class_stats[s.class_id]["submitted"] += 1
            class_stats[s.class_id]["total_score"] += score
        
        submissions.append({
            "studentId": str(s.student_id),
            "studentName": f"{s.first_name} {s.last_name}",
            "className": c_name,
            "status": status,
            "score": score,
            "maxScore": max_score,
            "submittedAt": resp.completed_at.isoformat() if resp else None
        })

    submitted_count = len(responses)
    avg_score = round(total_score / submitted_count, 1) if submitted_count else 0
    pass_rate = round((pass_count / submitted_count) * 100, 1) if submitted_count else 0
    
    class_wise_stats = []
    for cid, data in class_stats.items():
        avg = data["total_score"] / data["submitted"] if data["submitted"] > 0 else 0
        class_wise_stats.append({
            "className": data["className"],
            "total": data["total"],
            "submitted": data["submitted"],
            "avgScore": round(avg, 1)
        })
    
    return success_response({
        "id": template_id,
        "title": template.name,
        "description": template.description,
        "totalQuestions": len(template.questions or []),
        "totalStudentsAssigned": len(students),
        "studentsSubmitted": submitted_count,
        "studentsPending": len(students) - submitted_count,
        "avgScore": avg_score,
        "passRate": pass_rate,
        "submissions": submissions,
        "classWiseStats": class_wise_stats
    })


# ============== 13. TEACHER ACTIVITY DETAILS ==============

@router.get("/activities/{activity_id}/details")
async def get_teacher_activity_details(
    activity_id: UUID,
    teacher_id: UUID,
    days: int = Query(30, description="Number of days for analytics"),
    db: Session = Depends(get_db)
):
    """Detailed view of a specific activity for teacher's classes."""
    
    class_ids = get_teacher_class_ids(db, teacher_id)
    if not class_ids:
        raise HTTPException(status_code=403, detail="Teacher has no assigned classes")
    
    activity = db.query(ActivityEngine).filter(ActivityEngine.activity_id == str(activity_id)).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Get assignments for teacher's classes
    assignments = db.query(ActivityAssignment).filter(
        ActivityAssignment.activity_id == activity_id,
        ActivityAssignment.class_id.in_(class_ids)
    ).all()
    
    assigned_class_ids = [a.class_id for a in assignments]
    
    # Get students from assigned classes
    students = db.query(Student).filter(Student.class_id.in_(assigned_class_ids)).all() if assigned_class_ids else []
    
    # Get submissions
    submissions_data = db.query(ActivitySubmission).join(ActivityAssignment).filter(
        ActivityAssignment.activity_id == activity_id,
        ActivityAssignment.class_id.in_(class_ids)
    ).all()
    
    sub_map = {s.student_id: s for s in submissions_data}

    completions = []
    completed_count = 0
    
    for s in students:
        sub = sub_map.get(s.student_id)
        status = sub.status.value.lower() if sub else "pending"
        
        if status in ["submitted", "verified"]:
            completed_count += 1
            
        completions.append({
            "studentId": str(s.student_id),
            "studentName": f"{s.first_name} {s.last_name}",
            "status": status,
            "submittedAt": sub.submitted_at.isoformat() if sub and sub.submitted_at else None
        })
    
    return success_response({
        "id": activity_id,
        "title": activity.title,
        "type": activity.activity_type or "Activity",
        "totalStudentsAssigned": len(students),
        "studentsCompleted": completed_count,
        "studentsPending": len(students) - completed_count,
        "completions": completions
    })


# ============== 14. TEACHER WEBINAR DETAILS ==============

@router.get("/webinars/{webinar_id}/details")
async def get_teacher_webinar_details(
    webinar_id: UUID,
    teacher_id: UUID,
    db: Session = Depends(get_db)
):
    """Detailed view of a specific webinar for teacher's classes."""
    from app.models.webinar import Webinar
    
    class_ids = get_teacher_class_ids(db, teacher_id)
    if not class_ids:
        raise HTTPException(status_code=403, detail="Teacher has no assigned classes")
    
    webinar = db.query(Webinar).filter(Webinar.webinar_id == webinar_id).first()
    if not webinar:
        raise HTTPException(status_code=404, detail="Webinar not found")
    
    # Get students from teacher's classes
    students = db.query(Student).options(
        joinedload(Student.class_obj)
    ).filter(Student.class_id.in_(class_ids)).all()
    
    # Get attendance records
    attendance_records = db.query(StudentWebinarAttendance).filter(
        StudentWebinarAttendance.webinar_id == webinar_id,
        StudentWebinarAttendance.student_id.in_([s.student_id for s in students])
    ).all()
    
    attendance_map = {att.student_id: att for att in attendance_records}

    attendance_list = []
    class_wise_stats = {}
    
    for student in students:
        att = attendance_map.get(student.student_id)
        
        if att:
            status = "attended" if att.attended else "absent"
            attended = att.attended
            duration = att.watch_duration_minutes
            watch_percentage = round((att.watch_duration_minutes / webinar.duration_minutes * 100), 1) if att.watch_duration_minutes and webinar.duration_minutes else 0
        else:
            status = "absent"
            attended = False
            duration = None
            watch_percentage = 0
        
        class_name = student.class_obj.name if student.class_obj else "Unassigned"
        
        attendance_list.append({
            "studentId": str(student.student_id),
            "studentName": f"{student.first_name} {student.last_name}",
            "className": class_name,
            "status": status,
            "attended": attended,
            "duration": duration,
            "watchPercentage": watch_percentage
        })
        
        if class_name not in class_wise_stats:
            class_wise_stats[class_name] = {"attended": 0, "total": 0, "totalWatchTime": 0, "attendedCount": 0}
        
        class_wise_stats[class_name]["total"] += 1
        if attended:
            class_wise_stats[class_name]["attended"] += 1
            class_wise_stats[class_name]["attendedCount"] += 1
            class_wise_stats[class_name]["totalWatchTime"] += duration or 0

    class_wise_list = []
    for class_name, stats in class_wise_stats.items():
        avg_watch_time = stats["totalWatchTime"] / stats["attendedCount"] if stats["attendedCount"] > 0 else 0
        class_wise_list.append({
            "className": class_name,
            "attended": stats["attended"],
            "total": stats["total"],
            "avgWatchTime": round(avg_watch_time, 1)
        })
    
    total_invited = len(attendance_list)
    attended_count = sum(1 for a in attendance_list if a["status"] == "attended")
    attended_records = [a for a in attendance_list if a["attended"]]
    avg_watch_pct = sum(a["watchPercentage"] for a in attended_records) / len(attended_records) if attended_records else 0
    
    return success_response({
        "id": str(webinar_id),
        "title": webinar.title,
        "topic": webinar.category.value if webinar.category else "General",
        "description": webinar.description or "",
        "presenter": webinar.speaker_name or "",
        "scheduledDate": webinar.date.isoformat() if webinar.date else None,
        "duration": webinar.duration_minutes or 0,
        "totalStudentsInvited": total_invited,
        "studentsAttended": attended_count,
        "studentsAbsent": total_invited - attended_count,
        "avgWatchPercentage": round(avg_watch_pct, 1),
        "attendance": attendance_list,
        "classWiseStats": class_wise_list
    })


# ============== 15. TEACHER LEADERBOARD ==============

@router.get("/leaderboard")
async def get_teacher_leaderboard(
    teacher_id: UUID,
    type: str = Query(..., description="assessments, activities, webinars"),
    days: int = Query(30, description="Number of days for analytics"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Get top performing students from teacher's classes based on engagement type."""
    start_date, end_date = get_date_range(days)
    start_datetime = datetime.combine(start_date, datetime.min.time())
    
    class_ids = get_teacher_class_ids(db, teacher_id)
    if not class_ids:
        return success_response({"students": [], "total": 0, "page": page, "limit": limit})
    
    offset = (page - 1) * limit
    
    # Get students from teacher's classes
    students = db.query(Student).filter(Student.class_id.in_(class_ids)).all()
    student_map = {s.student_id: s for s in students}
    student_ids = list(student_map.keys())
    
    if not student_ids:
        return success_response({"students": [], "total": 0, "page": page, "limit": limit})
    
    # Get class names
    class_map = {c.class_id: c.name for c in db.query(Class).filter(Class.class_id.in_(class_ids)).all()}
    
    results = []
    total_count = 0

    if type == "assessments":
        base_query = db.query(
            StudentResponse.student_id,
            func.avg(StudentResponse.score).label('score'),
            func.count(func.distinct(StudentResponse.assessment_id)).label('count')
        ).filter(
            StudentResponse.student_id.in_(student_ids),
            StudentResponse.completed_at >= start_datetime
        ).group_by(StudentResponse.student_id)
        
        total_count = base_query.count()
        data = base_query.order_by(desc('score')).offset(offset).limit(limit).all()
        
        for row in data:
            s = student_map.get(row.student_id)
            if s:
                results.append({
                    "id": str(s.student_id),
                    "name": f"{s.first_name} {s.last_name}",
                    "className": class_map.get(s.class_id, "Unknown"),
                    "score": round(row.score, 1) if row.score else 0,
                    "scoreLabel": "Avg Score",
                    "secondaryScore": row.count,
                    "secondaryLabel": "Assessments",
                    "riskLevel": s.risk_level.value.lower() if s.risk_level else "low"
                })

    elif type == "activities":
        base_query = db.query(
            ActivitySubmission.student_id,
            func.count(ActivitySubmission.submission_id).label('count')
        ).filter(
            ActivitySubmission.student_id.in_(student_ids),
            ActivitySubmission.status.in_([SubmissionStatus.SUBMITTED, SubmissionStatus.VERIFIED]),
            ActivitySubmission.submitted_at >= start_datetime
        ).group_by(ActivitySubmission.student_id)
        
        total_count = base_query.count()
        data = base_query.order_by(desc('count')).offset(offset).limit(limit).all()
        
        for row in data:
            s = student_map.get(row.student_id)
            if s:
                results.append({
                    "id": str(s.student_id),
                    "name": f"{s.first_name} {s.last_name}",
                    "className": class_map.get(s.class_id, "Unknown"),
                    "score": row.count,
                    "scoreLabel": "Activities Completed",
                    "riskLevel": s.risk_level.value.lower() if s.risk_level else "low"
                })

    elif type == "webinars":
        base_query = db.query(
            StudentWebinarAttendance.student_id,
            func.count(StudentWebinarAttendance.id).label('count')
        ).filter(
            StudentWebinarAttendance.student_id.in_(student_ids),
            StudentWebinarAttendance.attended == True,
            StudentWebinarAttendance.created_at >= start_datetime
        ).group_by(StudentWebinarAttendance.student_id)
        
        total_count = base_query.count()
        data = base_query.order_by(desc('count')).offset(offset).limit(limit).all()
        
        for row in data:
            s = student_map.get(row.student_id)
            if s:
                results.append({
                    "id": str(s.student_id),
                    "name": f"{s.first_name} {s.last_name}",
                    "className": class_map.get(s.class_id, "Unknown"),
                    "score": row.count,
                    "scoreLabel": "Webinars Attended",
                    "riskLevel": s.risk_level.value.lower() if s.risk_level else "low"
                })

    return success_response({
        "students": results,
        "total": total_count,
        "page": page,
        "limit": limit
    })
