from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case as sql_case, String
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.core.database import get_db
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus, RiskLevel
from app.models.observation import Observation
from app.models.assessment import Assessment
from app.models.class_model import Class
from app.models.school import School
from app.schemas.user import UserCreate, UserResponse, UserUpdate

# Initialize logger
logger = get_logger(__name__)

router = APIRouter()

@router.post("/")
async def create_school_admin(
    admin_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Create a new principal/admin"""
    # Ensure role is principal or admin
    if admin_data.role not in [UserRole.PRINCIPAL, UserRole.ADMIN]:
        raise HTTPException(
            status_code=400,
            detail="Role must be 'principal' or 'admin' for this endpoint"
        )
    
    # Validate school exists
    school = db.query(School).filter(School.school_id == admin_data.school_id).first()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == admin_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    from app.core.security import get_password_hash
    
    # Convert Pydantic models to dict for JSON storage
    profile_dict = admin_data.profile.dict() if admin_data.profile and hasattr(admin_data.profile, 'dict') else admin_data.profile
    availability_dict = admin_data.availability.dict() if admin_data.availability and hasattr(admin_data.availability, 'dict') else admin_data.availability
    
    admin = User(
        email=admin_data.email,
        display_name=admin_data.display_name,
        role=admin_data.role,
        phone=admin_data.phone,
        school_id=admin_data.school_id,
        hashed_password=get_password_hash(admin_data.password),
        profile=profile_dict,
        availability=availability_dict
    )
    
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return success_response(admin)

@router.get("/")
async def list_school_admins(
    school_id: UUID,  # Required parameter
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all principals and admins in a school"""
    admins = db.query(User).filter(
        User.school_id == school_id,
        User.role.in_([UserRole.PRINCIPAL, UserRole.ADMIN])
    ).offset(skip).limit(limit).all()
    
    return success_response(admins)

@router.get("/{admin_id}")
async def get_school_admin(
    admin_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a specific principal/admin by ID"""
    admin = db.query(User).filter(
        User.user_id == admin_id,
        User.role.in_([UserRole.PRINCIPAL, UserRole.ADMIN])
    ).first()
    
    if not admin:
        raise HTTPException(status_code=404, detail="School admin not found")
    return success_response(admin)

@router.get("/dashboard/overview")
async def get_school_overview(
    school_id: UUID,  # Required parameter
    db: Session = Depends(get_db)
):
    """Get comprehensive school overview dashboard"""
    
    # 1. Total counts (Optimized: Single queries)
    total_students = db.query(User).filter(User.school_id == school_id, User.role == UserRole.STUDENT).count()
    total_classes = db.query(Class).filter(Class.school_id == school_id).count()
    total_teachers = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.TEACHER
    ).count()
    total_counsellors = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.COUNSELLOR
    ).count()
    
    # 2. Case Statistics (Optimized: Aggregations)
    # Join Case -> Student to filter by school_id directly in DB
    case_stats = db.query(
        func.count(Case.case_id).label('total'),
        func.sum(sql_case(
            (Case.status != CaseStatus.CLOSED, 1), else_=0
        )).label('active'),
        func.sum(sql_case(
            ((Case.risk_level == RiskLevel.CRITICAL) & (Case.status != CaseStatus.CLOSED), 1), else_=0
        )).label('critical'),
        func.sum(sql_case(
            ((Case.risk_level == RiskLevel.HIGH) & (Case.status != CaseStatus.CLOSED), 1), else_=0
        )).label('high'),
        func.sum(sql_case(
            ((Case.risk_level == RiskLevel.MEDIUM) & (Case.status != CaseStatus.CLOSED), 1), else_=0
        )).label('medium'),
        func.sum(sql_case(
            ((Case.risk_level == RiskLevel.LOW) & (Case.status != CaseStatus.CLOSED), 1), else_=0
        )).label('low')
    ).join(User, Case.student_id == User.user_id)\
     .filter(User.school_id == school_id, User.role == UserRole.STUDENT).first()

    total_cases = case_stats.total or 0
    active_cases = case_stats.active or 0
    critical_cases = case_stats.critical or 0
    high_risk_cases = case_stats.high or 0
    medium_risk_cases = case_stats.medium or 0
    low_risk_cases = case_stats.low or 0
    
    # 3. Recent Activity (Optimized)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    recent_observations = db.query(func.count(Observation.observation_id))\
        .join(User, Observation.student_id == User.user_id)\
        .filter(
            User.school_id == school_id,
            User.role == UserRole.STUDENT,
            Observation.timestamp >= thirty_days_ago
        ).scalar() or 0

    # 4. Assessment Analytics (Optimized)
    from app.models.assessment import StudentResponse, AssessmentTemplate
    
    # Recent assessments count
    recent_assessments_count = db.query(func.count(func.distinct(StudentResponse.assessment_id)))\
        .join(User, StudentResponse.student_id == User.user_id)\
        .filter(
            User.school_id == school_id,
            User.role == UserRole.STUDENT,
            StudentResponse.completed_at >= thirty_days_ago
        ).scalar() or 0
        
    # Assessment Stats Aggregation
    assessment_stats = db.query(
        func.count(StudentResponse.response_id).label('total_responses'),
        func.count(func.distinct(StudentResponse.student_id)).label('students_assessed'),
        func.avg(StudentResponse.score).label('avg_score')
    ).join(User, StudentResponse.student_id == User.user_id)\
     .filter(
         User.school_id == school_id,
         User.role == UserRole.STUDENT,
         StudentResponse.completed_at.isnot(None)
     ).first()
     
    students_assessed = assessment_stats.students_assessed or 0
    avg_assessment_score = float(assessment_stats.avg_score or 0)
    students_not_assessed = total_students - students_assessed
    assessment_completion_rate = (students_assessed / total_students * 100) if total_students > 0 else 0

    # Category Breakdown (Optimized Group By)
    category_stats = db.query(
        AssessmentTemplate.category,
        func.count(StudentResponse.response_id).label('count'),
        func.avg(StudentResponse.score).label('avg_score')
    ).select_from(StudentResponse)\
     .join(Assessment, StudentResponse.assessment_id == Assessment.assessment_id)\
     .join(AssessmentTemplate, Assessment.template_id == AssessmentTemplate.template_id)\
     .join(User, StudentResponse.student_id == User.user_id)\
     .filter(User.school_id == school_id, User.role == UserRole.STUDENT, StudentResponse.completed_at.isnot(None))\
     .group_by(AssessmentTemplate.category).all()
     
    category_breakdown = [
        {
            "category": stat.category or "General",
            "average_score": round(float(stat.avg_score or 0), 2),
            "total_assessments": stat.count
        }
        for stat in category_stats
    ]

    # Grade Breakdown (Optimized Group By)
    grade_stats = db.query(
        Class.grade,
        func.count(StudentResponse.response_id).label('count'),
        func.avg(StudentResponse.score).label('avg_score')
    ).select_from(StudentResponse)\
     .join(Student, StudentResponse.student_id == User.user_id)\
     .join(Class, User.profile["class_id"].astext == func.cast(Class.class_id, String))\
     .filter(User.school_id == school_id, StudentResponse.completed_at.isnot(None))\
     .group_by(Class.grade).all()
     
    grade_breakdown = [
        {
            "grade": stat.grade,
            "average_score": round(float(stat.avg_score or 0), 2),
            "total_assessments": stat.count
        }
        for stat in grade_stats
    ]
    grade_breakdown.sort(key=lambda x: x["grade"])

    # Trend Analysis (Optimized)
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    
    # Calculate averages for two periods in one query using conditional aggregation
    trend_stats = db.query(
        func.avg(sql_case(
            ((StudentResponse.completed_at >= sixty_days_ago) & (StudentResponse.completed_at < thirty_days_ago), StudentResponse.score),
            else_=None
        )).label('prev_avg'),
        func.avg(sql_case(
            (StudentResponse.completed_at >= thirty_days_ago, StudentResponse.score),
            else_=None
        )).label('curr_avg'),
        func.count(sql_case(
            ((StudentResponse.completed_at >= sixty_days_ago) & (StudentResponse.completed_at < thirty_days_ago), 1),
            else_=None
        )).label('prev_count'),
        func.count(sql_case(
            (StudentResponse.completed_at >= thirty_days_ago, 1),
            else_=None
        )).label('curr_count')
    ).join(Student, StudentResponse.student_id == User.user_id)\
     .filter(User.school_id == school_id).first()
     
    previous_avg = float(trend_stats.prev_avg or 0)
    recent_avg = float(trend_stats.curr_avg or 0)
    
    trend = "improving" if recent_avg > previous_avg else "declining" if recent_avg < previous_avg else "stable"
    trend_change = round(((recent_avg - previous_avg) / previous_avg * 100), 2) if previous_avg > 0 else 0

    # At-risk percentage
    at_risk_students = critical_cases + high_risk_cases + medium_risk_cases
    at_risk_percent = (at_risk_students / total_students * 100) if total_students > 0 else 0

    # 5. Monthly Trends (Optimized: Single Query Grouped by Month)
    from sqlalchemy import text
    
    # We'll use a recursive CTE or generate_series to ensure all months are present, 
    # but for simplicity and DB compatibility, we'll query grouped data and merge in Python.
    six_months_ago = datetime.utcnow() - relativedelta(months=5)
    six_months_ago = six_months_ago.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Group Cases by Month
    cases_trend = db.query(
        func.date_trunc('month', Case.created_at).label('month'),
        func.count(Case.case_id).label('opened'),
        func.count(Case.closed_at).label('closed') # This is approximate as closed_at might be in different month
    ).join(Student, Case.student_id == User.user_id)\
     .filter(User.school_id == school_id, Case.created_at >= six_months_ago)\
     .group_by(text('1')).all()
     
    # Better approach for closed cases: group by closed_at
    cases_closed_trend = db.query(
        func.date_trunc('month', Case.closed_at).label('month'),
        func.count(Case.case_id).label('closed')
    ).join(Student, Case.student_id == User.user_id)\
     .filter(User.school_id == school_id, Case.closed_at >= six_months_ago)\
     .group_by(text('1')).all()

    # Group Assessments by Month
    assessments_trend = db.query(
        func.date_trunc('month', StudentResponse.completed_at).label('month'),
        func.count(StudentResponse.response_id).label('count'),
        func.avg(StudentResponse.score).label('avg_score')
    ).join(Student, StudentResponse.student_id == User.user_id)\
     .filter(User.school_id == school_id, StudentResponse.completed_at >= six_months_ago)\
     .group_by(text('1')).all()

    # Merge Data in Python
    monthly_data = {}
    
    # Initialize last 6 months
    for i in range(5, -1, -1):
        month_date = datetime.utcnow() - relativedelta(months=i)
        key = month_date.strftime("%Y-%m")
        monthly_data[key] = {
            "month": month_date.strftime("%b %Y"),
            "wellbeingIndex": 0,
            "casesOpened": 0,
            "casesClosed": 0,
            "assessmentsCompleted": 0
        }

    for r in cases_trend:
        if r.month:
            key = r.month.strftime("%Y-%m")
            if key in monthly_data:
                monthly_data[key]["casesOpened"] = r.opened

    for r in cases_closed_trend:
        if r.month:
            key = r.month.strftime("%Y-%m")
            if key in monthly_data:
                monthly_data[key]["casesClosed"] = r.closed

    for r in assessments_trend:
        if r.month:
            key = r.month.strftime("%Y-%m")
            if key in monthly_data:
                monthly_data[key]["assessmentsCompleted"] = r.count
                monthly_data[key]["wellbeingIndex"] = round(float(r.avg_score or 0), 1)

    monthly_trends = list(monthly_data.values())

    # 6. Class Metrics (Optimized: Single Query with Joins)
    # This is complex to do in one query due to multiple aggregations. 
    # We will fetch class info + at_risk count + avg score in separate grouped queries and merge.
    
    classes = db.query(Class).options(joinedload(Class.teacher)).filter(Class.school_id == school_id).all()
    
    # Count students per class
    class_student_counts = db.query(
        User.profile["class_id"].astext, func.count(User.user_id)
    ).filter(User.school_id == school_id).group_by(User.profile["class_id"].astext).all()
    student_count_map = {c[0]: c[1] for c in class_student_counts}
    
    # Count at-risk students per class
    class_risk_counts = db.query(
        User.profile["class_id"].astext, func.count(func.distinct(User.user_id))
    ).join(Case, User.user_id == Case.student_id)\
     .filter(
         User.school_id == school_id,
         Case.status != CaseStatus.CLOSED,
         Case.risk_level.in_([RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL])
     ).group_by(User.profile["class_id"].astext).all()
    risk_count_map = {c[0]: c[1] for c in class_risk_counts}
    
    # Avg wellbeing per class
    class_wellbeing_scores = db.query(
        User.profile["class_id"].astext, func.avg(StudentResponse.score)
    ).join(StudentResponse, User.user_id == StudentResponse.student_id)\
     .filter(User.school_id == school_id, StudentResponse.score.isnot(None))\
     .group_by(User.profile["class_id"].astext).all()
    wellbeing_map = {c[0]: float(c[1] or 0) for c in class_wellbeing_scores}

    class_metrics = []
    for cls in classes:
        class_metrics.append({
            "id": str(cls.class_id),
            "name": cls.name,
            "grade": cls.grade,
            "section": cls.section or "",
            "teacher": cls.teacher.display_name if cls.teacher else "Unassigned",
            "totalStudents": student_count_map.get(cls.class_id, 0),
            "wellbeingIndex": round(wellbeing_map.get(cls.class_id, 0), 1),
            "atRiskCount": risk_count_map.get(cls.class_id, 0)
        })
    
    class_metrics.sort(key=lambda x: (x["grade"], x["section"]))

    return success_response({
        "school_id": str(school_id),
        "overview": {
            "total_students": total_students,
            "total_classes": total_classes,
            "total_teachers": total_teachers,
            "total_counsellors": total_counsellors
        },
        "mental_health_metrics": {
            "total_cases": total_cases,
            "active_cases": active_cases,
            "closed_cases": total_cases - active_cases,
            "at_risk_students": at_risk_students,
            "at_risk_percentage": round(at_risk_percent, 2)
        },
        "cases_by_risk_level": {
            "critical": critical_cases,
            "high": high_risk_cases,
            "medium": medium_risk_cases,
            "low": low_risk_cases
        },
        "assessment_analytics": {
            "total_assessments_completed": int(assessment_stats.total_responses or 0) if assessment_stats else 0,
            "recent_assessments_30_days": recent_assessments_count,
            "students_assessed": students_assessed,
            "students_not_assessed": students_not_assessed,
            "assessment_completion_rate": round(assessment_completion_rate, 1),
            "average_assessment_score": round(avg_assessment_score, 2),
            "by_category": category_breakdown,
            "by_grade": grade_breakdown,
            "trend_analysis": {
                "trend": trend,
                "change_percentage": trend_change,
                "previous_period_avg": round(previous_avg, 2),
                "recent_period_avg": round(recent_avg, 2),
                "previous_period_count": trend_stats.prev_count or 0,
                "recent_period_count": trend_stats.curr_count or 0
            }
        },
        "recent_activity_30_days": {
            "observations": recent_observations,
            "assessments_completed": recent_assessments_count
        },
        "monthly_trends": monthly_trends,
        "class_metrics": class_metrics,
        "counsellor_workload": []  # Will be populated by separate endpoint
    })

@router.get("/dashboard/at-risk-students")
async def get_at_risk_students(
    school_id: UUID,  # Required parameter
    risk_level: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get list of at-risk students with their case details"""
    
    # Get all students for this school
    student_ids = [s.user_id for s in db.query(User.user_id).filter(User.school_id == school_id).all()]
    
    # Query active cases with eager loading
    query = db.query(Case).options(
        joinedload(Case.student)
    ).filter(
        Case.student_id.in_(student_ids),
        Case.status != CaseStatus.CLOSED
    )
    
    if risk_level:
        query = query.filter(Case.risk_level == risk_level)
    else:
        # Default: show medium, high, and critical only
        query = query.filter(Case.risk_level.in_([RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]))
    
    cases = query.offset(skip).limit(limit).all()
    
    # Batch load counsellors
    counsellor_ids = [c.assigned_counsellor for c in cases if c.assigned_counsellor]
    counsellors_map = {}
    if counsellor_ids:
        counsellors = db.query(User).filter(User.user_id.in_(counsellor_ids)).all()
        counsellors_map = {c.user_id: c for c in counsellors}
    
    result = []
    for case in cases:
        student = case.student
        counsellor = counsellors_map.get(case.assigned_counsellor) if case.assigned_counsellor else None
        
        # Get parent information from student's profile
        parents_data = []
        if student and student.profile:
            parent_email = student.profile.get("parent_email")
            parent_phone = student.profile.get("parent_phone")
            if parent_email or parent_phone:
                parent_info = {
                    "name": "Parent/Guardian",
                    "relationship": "Parent/Guardian",
                    "phone": parent_phone,
                    "email": parent_email,
                    "is_primary": True,
                    "consent_given": student.profile.get("consent_status") == "GRANTED" if student.profile.get("consent_status") else None
                }
                parents_data.append(parent_info)
        
        # Get student info from profile
        first_name = student.display_name.split()[0] if student and student.display_name else "Unknown"
        last_name = " ".join(student.display_name.split()[1:]) if student and student.display_name and len(student.display_name.split()) > 1 else ""
        class_id = student.profile.get("class_id") if student and student.profile else None
        
        result.append({
            "case_id": str(case.case_id),
            "student": {
                "student_id": str(student.user_id) if student else None,
                "name": student.display_name if student else "Unknown",
                "class_id": class_id
            },
            "risk_level": case.risk_level.value,
            "status": case.status.value,
            "tags": case.tags,
            "assigned_counsellor": counsellor.display_name if counsellor else None,
            "created_at": case.created_at.isoformat(),
            "days_open": (datetime.utcnow() - case.created_at).days,
            "parents": parents_data
        })
    
    return success_response({
        "school_id": str(school_id),
        "total_at_risk": len(result),
        "students": result
    })

@router.get("/dashboard/counsellor-workload")
async def get_counsellor_workload(
    school_id: UUID,  # Required parameter
    db: Session = Depends(get_db)
):
    """Get workload distribution across counsellors"""
    
    counsellors = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.COUNSELLOR
    ).all()
    
    # Batch load all cases for these counsellors
    counsellor_ids = [c.user_id for c in counsellors]
    all_cases = db.query(Case).filter(
        Case.assigned_counsellor.in_(counsellor_ids)
    ).all() if counsellor_ids else []
    
    # Group cases by counsellor
    cases_by_counsellor = {}
    for case in all_cases:
        if case.assigned_counsellor not in cases_by_counsellor:
            cases_by_counsellor[case.assigned_counsellor] = []
        cases_by_counsellor[case.assigned_counsellor].append(case)
    
    workload = []
    for counsellor in counsellors:
        counsellor_cases = cases_by_counsellor.get(counsellor.user_id, [])
        total_cases = len(counsellor_cases)
        active_cases = sum(1 for c in counsellor_cases if c.status != CaseStatus.CLOSED)
        critical = sum(1 for c in counsellor_cases if c.risk_level == RiskLevel.CRITICAL and c.status != CaseStatus.CLOSED)
        high = sum(1 for c in counsellor_cases if c.risk_level == RiskLevel.HIGH and c.status != CaseStatus.CLOSED)
        
        workload.append({
            "counsellor_id": str(counsellor.user_id),
            "name": counsellor.display_name,
            "email": counsellor.email,
            "total_cases": total_cases,
            "active_cases": active_cases,
            "high_priority_cases": critical + high,
            "availability": counsellor.availability
        })
    
    return success_response({
        "school_id": str(school_id),
        "total_counsellors": len(counsellors),
        "workload": workload
    })

@router.get("/dashboard/grade-level-analysis")
async def get_grade_level_analysis(
    school_id: UUID,  # Required parameter
    db: Session = Depends(get_db)
):
    """Get mental health metrics by grade level"""
    
    classes = db.query(Class).filter(Class.school_id == school_id).all()
    
    grade_data = {}
    for class_obj in classes:
        grade = class_obj.grade
        if grade not in grade_data:
            grade_data[grade] = {
                "grade": grade,
                "total_students": 0,
                "total_classes": 0,
                "active_cases": 0,
                "observations": 0
            }
        
        # Count students in this class
        students_count = db.query(User).filter(User.role == UserRole.STUDENT).filter(User.profile["class_id"].astext == str(class_obj.class_id)).count()
        grade_data[grade]["total_students"] += students_count
        grade_data[grade]["total_classes"] += 1
        
        # Get student IDs for this class
        student_ids = [s.user_id for s in db.query(User.user_id).filter(User.profile["class_id"].astext == str(class_obj.class_id)).all()]
        
        # Count active cases
        active_cases = db.query(Case).filter(
            Case.student_id.in_(student_ids),
            Case.status != CaseStatus.CLOSED
        ).count()
        grade_data[grade]["active_cases"] += active_cases
        
        # Count observations (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        observations = db.query(Observation).filter(
            Observation.student_id.in_(student_ids),
            Observation.timestamp >= thirty_days_ago
        ).count()
        grade_data[grade]["observations"] += observations
    
    # Calculate percentages
    for grade in grade_data:
        total = grade_data[grade]["total_students"]
        if total > 0:
            grade_data[grade]["case_rate_percent"] = round(
                (grade_data[grade]["active_cases"] / total) * 100, 2
            )
        else:
            grade_data[grade]["case_rate_percent"] = 0
    
    return success_response({
        "school_id": str(school_id),
        "grade_levels": list(grade_data.values())
    })

@router.get("/reports/monthly-summary")
async def get_monthly_summary(
    school_id: UUID,  # Required parameter
    year: int,
    month: int,
    db: Session = Depends(get_db)
):
    """Get monthly summary report"""
    
    from datetime import date
    from calendar import monthrange
    from app.models.assessment import StudentResponse
    
    # Get date range for the month
    _, last_day = monthrange(year, month)
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, last_day, 23, 59, 59)
    
    # Get all students for this school
    student_ids = [s.user_id for s in db.query(User.user_id).filter(User.school_id == school_id).all()]
    
    # Cases created this month
    cases_created = db.query(Case).filter(
        Case.student_id.in_(student_ids),
        Case.created_at >= start_date,
        Case.created_at <= end_date
    ).count()
    
    # Cases closed this month
    cases_closed = db.query(Case).filter(
        Case.student_id.in_(student_ids),
        Case.closed_at >= start_date,
        Case.closed_at <= end_date
    ).count()
    
    # Observations this month
    observations = db.query(Observation).filter(
        Observation.student_id.in_(student_ids),
        Observation.timestamp >= start_date,
        Observation.timestamp <= end_date
    ).count()
    
    # Assessments completed this month (distinct assessments)
    assessments = db.query(StudentResponse).filter(
        StudentResponse.student_id.in_(student_ids),
        StudentResponse.completed_at >= start_date,
        StudentResponse.completed_at <= end_date
    ).distinct(StudentResponse.assessment_id).count() if student_ids else 0
    
    return success_response({
        "school_id": str(school_id),
        "period": f"{year}-{month:02d}",
        "summary": {
            "cases_created": cases_created,
            "cases_closed": cases_closed,
            "observations_recorded": observations,
            "assessments_completed": assessments
        }
    })

@router.patch("/{admin_id}")
async def update_school_admin(
    admin_id: UUID,
    admin_update: UserUpdate,
    db: Session = Depends(get_db)
):
    """Update school admin information"""
    admin = db.query(User).filter(
        User.user_id == admin_id,
        User.role.in_([UserRole.PRINCIPAL, UserRole.ADMIN])
    ).first()
    
    if not admin:
        raise HTTPException(status_code=404, detail="School admin not found")
    
    update_data = admin_update.dict(exclude_unset=True)
    
    # Convert Pydantic models to dict for JSON storage
    if 'profile' in update_data and update_data['profile'] is not None:
        if hasattr(update_data['profile'], 'dict'):
            update_data['profile'] = update_data['profile'].dict()
    
    if 'availability' in update_data and update_data['availability'] is not None:
        if hasattr(update_data['availability'], 'dict'):
            update_data['availability'] = update_data['availability'].dict()
    
    for field, value in update_data.items():
        setattr(admin, field, value)
    
    db.commit()
    db.refresh(admin)
    return success_response(admin)

@router.delete("/{admin_id}")
async def delete_school_admin(
    admin_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete a school admin"""
    admin = db.query(User).filter(
        User.user_id == admin_id,
        User.role.in_([UserRole.PRINCIPAL, UserRole.ADMIN])
    ).first()
    
    if not admin:
        raise HTTPException(status_code=404, detail="School admin not found")
    
    db.delete(admin)
    db.commit()
    return success_response({"message": "School admin deleted successfully", "admin_id": str(admin_id)})
