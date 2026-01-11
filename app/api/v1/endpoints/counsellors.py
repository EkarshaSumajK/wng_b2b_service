from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from app.core.database import get_db
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.models.user import User, UserRole
from app.models.case import Case
from app.models.school import School
from app.schemas.user import UserCreate, UserResponse, UserUpdate

# Initialize logger
logger = get_logger(__name__)

router = APIRouter()

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_counsellor(
    counsellor_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Create a new counsellor"""
    logger.info(f"Creating counsellor: {counsellor_data.email}")
    
    # Ensure role is counsellor
    if counsellor_data.role != UserRole.COUNSELLOR:
        logger.warning(f"Counsellor creation failed - invalid role")
        raise HTTPException(
            status_code=400,
            detail="Role must be 'counsellor' for this endpoint"
        )

    # Validate school exists
    school = db.query(School).filter(School.school_id == counsellor_data.school_id).first()
    if not school:
        logger.warning(f"Counsellor creation failed - school not found: {counsellor_data.school_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == counsellor_data.email).first()
    if existing_user:
        logger.warning(f"Counsellor creation failed - email exists: {counsellor_data.email}")
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    from app.core.security import get_password_hash

    # Convert Pydantic models to dict for JSON storage
    profile_dict = counsellor_data.profile.dict() if counsellor_data.profile and hasattr(counsellor_data.profile, 'dict') else counsellor_data.profile
    availability_dict = counsellor_data.availability.dict() if counsellor_data.availability and hasattr(counsellor_data.availability, 'dict') else counsellor_data.availability

    counsellor = User(
        email=counsellor_data.email,
        display_name=counsellor_data.display_name,
        role=UserRole.COUNSELLOR,
        phone=counsellor_data.phone,
        school_id=counsellor_data.school_id,
        hashed_password=get_password_hash(counsellor_data.password),
        profile=profile_dict,
        availability=availability_dict
    )

    db.add(counsellor)
    db.commit()
    db.refresh(counsellor)
    logger.info(f"Counsellor created", extra={"extra_data": {"counsellor_id": str(counsellor.user_id)}})
    return success_response(counsellor)

@router.get("")
async def list_counsellors(
    school_id: UUID,  # Required parameter
    skip: int = 0,
    limit: int = 100,
    specialization: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all counsellors in a school"""
    logger.debug(f"Listing counsellors for school: {school_id}")
    query = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.COUNSELLOR
    )

    # Filter by specialization if provided
    if specialization:
        query = query.filter(
            User.profile.contains({"specializations": [specialization]})
        )

    counsellors = query.offset(skip).limit(limit).all()
    logger.debug(f"Found {len(counsellors)} counsellors")
    return success_response(counsellors)

@router.get("/{counsellor_id}")
async def get_counsellor(
    counsellor_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a specific counsellor by ID"""
    counsellor = db.query(User).filter(
        User.user_id == counsellor_id,
        User.role == UserRole.COUNSELLOR
    ).first()

    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")
    return success_response(counsellor)

@router.get("/{counsellor_id}/cases")
async def get_counsellor_cases(
    counsellor_id: UUID,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all cases assigned to a counsellor"""
    counsellor = db.query(User).filter(
        User.user_id == counsellor_id,
        User.role == UserRole.COUNSELLOR
    ).first()

    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")

    query = db.query(Case).filter(Case.assigned_counsellor == counsellor_id)

    if status:
        query = query.filter(Case.status == status)

    if risk_level:
        query = query.filter(Case.risk_level == risk_level)

    cases = query.all()

    return success_response([
        {
            "case_id": str(c.case_id),
            "student_id": str(c.student_id),
            "status": c.status.value,
            "risk_level": c.risk_level.value,
            "tags": c.tags,
            "created_at": c.created_at.isoformat(),
            "closed_at": c.closed_at.isoformat() if c.closed_at else None
        }
        for c in cases
    ])

@router.get("/{counsellor_id}/dashboard")
async def get_counsellor_dashboard(
    counsellor_id: UUID,
    db: Session = Depends(get_db)
):
    """Get comprehensive counsellor dashboard with caseload and student assessment data"""
    counsellor = db.query(User).filter(
        User.user_id == counsellor_id,
        User.role == UserRole.COUNSELLOR
    ).first()

    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")

    from app.models.case import CaseStatus, RiskLevel
    from app.models.assessment import Assessment, StudentResponse, AssessmentTemplate
    from datetime import datetime, timedelta

    # Get all cases
    all_cases = db.query(Case).filter(Case.assigned_counsellor == counsellor_id).all()

    # Calculate case statistics
    total_cases = len(all_cases)
    active_cases = len([c for c in all_cases if c.status != CaseStatus.CLOSED])
    closed_cases = len([c for c in all_cases if c.status == CaseStatus.CLOSED])

    # By risk level
    critical = len([c for c in all_cases if c.risk_level == RiskLevel.CRITICAL and c.status != CaseStatus.CLOSED])
    high = len([c for c in all_cases if c.risk_level == RiskLevel.HIGH and c.status != CaseStatus.CLOSED])
    medium = len([c for c in all_cases if c.risk_level == RiskLevel.MEDIUM and c.status != CaseStatus.CLOSED])
    low = len([c for c in all_cases if c.risk_level == RiskLevel.LOW and c.status != CaseStatus.CLOSED])

    # By status
    intake = len([c for c in all_cases if c.status == CaseStatus.INTAKE])
    assessment_status = len([c for c in all_cases if c.status == CaseStatus.ASSESSMENT])
    intervention = len([c for c in all_cases if c.status == CaseStatus.INTERVENTION])
    monitoring = len([c for c in all_cases if c.status == CaseStatus.MONITORING])

    # Get student IDs from cases
    student_ids = [c.student_id for c in all_cases]
    
    # === ASSESSMENT DATA ===
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Get all completed assessments for these students with eager loading
    all_completed_responses = db.query(StudentResponse).options(
        joinedload(StudentResponse.assessment).joinedload(Assessment.template)
    ).filter(
        StudentResponse.student_id.in_(student_ids),
        StudentResponse.completed_at.isnot(None)
    ).all() if student_ids else []
    
    # Calculate assessment analytics
    assessment_scores = []
    assessment_by_category = {}
    student_assessment_data = {}
    
    for response in all_completed_responses:
        if response.score is not None:
            assessment_scores.append(response.score)
        
        # Track by student
        if response.student_id not in student_assessment_data:
            student_assessment_data[response.student_id] = {
                "total_score": 0,
                "count": 0,
                "scores": []
            }
        student_assessment_data[response.student_id]["total_score"] += response.score or 0
        student_assessment_data[response.student_id]["count"] += 1
        student_assessment_data[response.student_id]["scores"].append(response.score)
        
        # Get assessment category from eager-loaded relationship
        if response.assessment and response.assessment.template:
            category = response.assessment.template.category or "General"
            if category not in assessment_by_category:
                assessment_by_category[category] = {"total_score": 0, "count": 0, "scores": []}
            if response.score is not None:
                assessment_by_category[category]["total_score"] += response.score
                assessment_by_category[category]["count"] += 1
                assessment_by_category[category]["scores"].append(response.score)
    
    # Calculate statistics
    avg_assessment_score = sum(assessment_scores) / len(assessment_scores) if assessment_scores else 0
    students_assessed = len(student_assessment_data)
    
    # Category breakdown
    category_breakdown = []
    for category, data in assessment_by_category.items():
        avg_score = data["total_score"] / data["count"] if data["count"] > 0 else 0
        category_breakdown.append({
            "category": category,
            "average_score": round(avg_score, 2),
            "total_assessments": data["count"],
            "min_score": round(min(data["scores"]), 2) if data["scores"] else 0,
            "max_score": round(max(data["scores"]), 2) if data["scores"] else 0
        })
    
    # Pre-load all students at once (from b2b_users with role=STUDENT)
    students_map = {}
    if student_ids:
        students_list = db.query(User).filter(
            User.user_id.in_(student_ids),
            User.role == UserRole.STUDENT
        ).all()
        students_map = {s.user_id: s for s in students_list}
    
    # Students with concerning assessment scores (below average by 20%)
    concern_threshold = avg_assessment_score * 0.8 if avg_assessment_score > 0 else 0
    students_at_risk_by_assessment = []
    
    for student_id, data in student_assessment_data.items():
        avg_student_score = data["total_score"] / data["count"] if data["count"] > 0 else 0
        if avg_student_score < concern_threshold and avg_student_score > 0:
            student = students_map.get(student_id)
            case = next((c for c in all_cases if c.student_id == student_id), None)
            
            students_at_risk_by_assessment.append({
                "student_id": str(student_id),
                "student_name": student.display_name if student else "Unknown",
                "average_score": round(avg_student_score, 2),
                "assessments_completed": data["count"],
                "has_active_case": case is not None and case.status != CaseStatus.CLOSED,
                "risk_level": case.risk_level.value if case and case.status != CaseStatus.CLOSED else None
            })
    
    # Detailed list of all students in caseload with assessment completion
    students_assessment_details = []
    for case in all_cases:
        student = students_map.get(case.student_id)
        if student:
            student_data = student_assessment_data.get(case.student_id, {"total_score": 0, "count": 0, "scores": []})
            assessments_count = len(set(r.assessment_id for r in all_completed_responses if r.student_id == case.student_id))
            avg_score = student_data["total_score"] / student_data["count"] if student_data["count"] > 0 else 0
            
            # Get last assessment date
            student_responses = [r for r in all_completed_responses if r.student_id == case.student_id]
            last_assessment = max(student_responses, key=lambda r: r.completed_at if r.completed_at else datetime.min) if student_responses else None
            
            students_assessment_details.append({
                "student_id": str(case.student_id),
                "student_name": student.display_name,
                "case_status": case.status.value,
                "risk_level": case.risk_level.value,
                "assessments_completed": assessments_count,
                "total_responses": student_data["count"],
                "average_score": round(avg_score, 2) if avg_score > 0 else None,
                "last_assessment_date": last_assessment.completed_at.isoformat() if last_assessment and last_assessment.completed_at else None,
                "has_assessments": assessments_count > 0
            })
    
    # Sort by assessments completed (descending)
    students_assessment_details.sort(key=lambda x: x["assessments_completed"], reverse=True)
    
    # Count students without assessments
    students_without_assessments = len([s for s in students_assessment_details if not s["has_assessments"]])
    
    # Recent assessments for these students (distinct by assessment)
    recent_assessments_count = db.query(StudentResponse).filter(
        StudentResponse.student_id.in_(student_ids),
        StudentResponse.completed_at >= thirty_days_ago
    ).distinct(StudentResponse.assessment_id).count() if student_ids else 0

    # === CALENDAR METRICS ===
    from app.models.calendar_event import CalendarEvent, EventStatus
    from sqlalchemy import or_

    now = datetime.utcnow()
    # Adjust for IST (UTC+5:30) for "today" calculation if needed, but for now using UTC date
    # Ideally, we should handle timezone properly. Assuming server is UTC.
    # To match frontend "today", we might need to be careful.
    # Let's stick to UTC for now or basic date comparison.
    
    today_start = datetime.combine(now.date(), datetime.min.time())
    today_end = datetime.combine(now.date(), datetime.max.time())
    
    # Query for today's sessions
    todays_sessions_count = db.query(CalendarEvent).filter(
        or_(
            CalendarEvent.created_by == counsellor_id,
            CalendarEvent.attendees.any(counsellor_id)
        ),
        CalendarEvent.start_time >= today_start,
        CalendarEvent.start_time <= today_end,
        CalendarEvent.status.notin_([EventStatus.CANCELLED, EventStatus.COMPLETED])
    ).count()
    
    # Query for next session
    next_session = db.query(CalendarEvent).filter(
        or_(
            CalendarEvent.created_by == counsellor_id,
            CalendarEvent.attendees.any(counsellor_id)
        ),
        CalendarEvent.start_time > now,
        CalendarEvent.status.notin_([EventStatus.CANCELLED, EventStatus.COMPLETED])
    ).order_by(CalendarEvent.start_time).first()
    
    next_session_data = None
    if next_session:
        student_name = next_session.title # Default fallback
        if next_session.related_student_id:
             # Try to fetch student name if linked (from b2b_users)
             student = db.query(User).filter(
                 User.user_id == next_session.related_student_id,
                 User.role == UserRole.STUDENT
             ).first()
             if student:
                 student_name = student.display_name
        
        next_session_data = {
            "title": next_session.title,
            "start_time": next_session.start_time.isoformat(),
            "student_name": student_name
        }

    return success_response({
        "counsellor_id": str(counsellor_id),
        "counsellor_name": counsellor.display_name,
        "caseload": {
            "total_cases": total_cases,
            "active_cases": active_cases,
            "closed_cases": closed_cases,
            "by_risk_level": {
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low
            },
            "by_status": {
                "intake": intake,
                "assessment": assessment_status,
                "intervention": intervention,
                "monitoring": monitoring,
                "closed": closed_cases
            }
        },
        "assessment_analytics": {
            "total_students_assessed": students_assessed,
            "students_without_assessments": students_without_assessments,
            "total_assessments_completed": len(all_completed_responses),
            "recent_assessments_30_days": recent_assessments_count,
            "average_assessment_score": round(avg_assessment_score, 2),
            "by_category": category_breakdown,
            "students_at_risk_by_assessment": students_at_risk_by_assessment[:10],  # Top 10
            "student_assessment_details": students_assessment_details
        },
        "calendar_metrics": {
            "todays_sessions_count": todays_sessions_count,
            "next_session": next_session_data
        }
    })

@router.get("/{counsellor_id}/caseload")
async def get_counsellor_caseload(
    counsellor_id: UUID,
    db: Session = Depends(get_db)
):
    """Get counsellor's caseload statistics (legacy endpoint - use /dashboard instead)"""
    counsellor = db.query(User).filter(
        User.user_id == counsellor_id,
        User.role == UserRole.COUNSELLOR
    ).first()

    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")

    from app.models.case import CaseStatus, RiskLevel

    # Get all cases
    all_cases = db.query(Case).filter(Case.assigned_counsellor == counsellor_id).all()

    # Calculate statistics
    total_cases = len(all_cases)
    active_cases = len([c for c in all_cases if c.status != CaseStatus.CLOSED])
    closed_cases = len([c for c in all_cases if c.status == CaseStatus.CLOSED])

    # By risk level
    critical = len([c for c in all_cases if c.risk_level == RiskLevel.CRITICAL and c.status != CaseStatus.CLOSED])
    high = len([c for c in all_cases if c.risk_level == RiskLevel.HIGH and c.status != CaseStatus.CLOSED])
    medium = len([c for c in all_cases if c.risk_level == RiskLevel.MEDIUM and c.status != CaseStatus.CLOSED])
    low = len([c for c in all_cases if c.risk_level == RiskLevel.LOW and c.status != CaseStatus.CLOSED])

    # By status
    intake = len([c for c in all_cases if c.status == CaseStatus.INTAKE])
    assessment = len([c for c in all_cases if c.status == CaseStatus.ASSESSMENT])
    intervention = len([c for c in all_cases if c.status == CaseStatus.INTERVENTION])
    monitoring = len([c for c in all_cases if c.status == CaseStatus.MONITORING])

    return success_response({
        "counsellor_id": str(counsellor_id),
        "counsellor_name": counsellor.display_name,
        "total_cases": total_cases,
        "active_cases": active_cases,
        "closed_cases": closed_cases,
        "by_risk_level": {
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low
        },
        "by_status": {
            "intake": intake,
            "assessment": assessment,
            "intervention": intervention,
            "monitoring": monitoring,
            "closed": closed_cases
        }
    })

@router.patch("/{counsellor_id}")
async def update_counsellor(
    counsellor_id: UUID,
    counsellor_update: UserUpdate,
    db: Session = Depends(get_db)
):
    """Update counsellor information"""
    counsellor = db.query(User).filter(
        User.user_id == counsellor_id,
        User.role == UserRole.COUNSELLOR
    ).first()

    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")

    update_data = counsellor_update.dict(exclude_unset=True)

    # Convert Pydantic models to dict for JSON storage
    if 'profile' in update_data and update_data['profile'] is not None:
        if hasattr(update_data['profile'], 'dict'):
            update_data['profile'] = update_data['profile'].dict()

    if 'availability' in update_data and update_data['availability'] is not None:
        if hasattr(update_data['availability'], 'dict'):
            update_data['availability'] = update_data['availability'].dict()

    for field, value in update_data.items():
        setattr(counsellor, field, value)

    db.commit()
    db.refresh(counsellor)
    return success_response(counsellor)

@router.delete("/{counsellor_id}")
async def delete_counsellor(
    counsellor_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete a counsellor"""
    counsellor = db.query(User).filter(
        User.user_id == counsellor_id,
        User.role == UserRole.COUNSELLOR
    ).first()

    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")

    # Check if counsellor has assigned cases
    cases = db.query(Case).filter(Case.assigned_counsellor == counsellor_id).count()
    if cases > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete counsellor. They have {cases} assigned case(s). Please reassign cases first."
        )

    db.delete(counsellor)
    db.commit()
    return success_response({"message": "Counsellor deleted successfully", "counsellor_id": str(counsellor_id)})
