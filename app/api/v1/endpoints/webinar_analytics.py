"""
Webinar Analytics API
Provides analytics for webinars including attendance, engagement, and participant tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, and_, or_
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta, date

from app.core.database import get_db
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.models.webinar import Webinar, WebinarStatus, WebinarSchoolRegistration, RegistrationType, RegistrationStatus
from app.models.student import Student
from app.models.class_model import Class
from app.models.school import School
from app.models.user import User
from app.models.student_engagement import StudentWebinarAttendance
from pydantic import BaseModel

logger = get_logger(__name__)
router = APIRouter()


# ============== 1. WEBINAR LIST WITH ANALYTICS ==============

@router.get("")
async def get_webinars_analytics(
    school_id: Optional[UUID] = None,
    status: Optional[str] = None,
    days: int = Query(90, description="Filter to last N days"),
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get webinars with attendance analytics - only shows webinars registered by the school."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # If school_id provided, only show webinars the school has registered for
    if school_id:
        # Get webinar IDs that this school has registered for
        registered_webinar_ids = db.query(WebinarSchoolRegistration.webinar_id).filter(
            WebinarSchoolRegistration.school_id == school_id
        ).all()
        registered_ids = [r.webinar_id for r in registered_webinar_ids]
        
        if not registered_ids:
            return success_response({
                "total": 0,
                "skip": skip,
                "limit": limit,
                "webinars": []
            })
        
        query = db.query(Webinar).filter(Webinar.webinar_id.in_(registered_ids))
    else:
        # No school filter - show all webinars (admin view)
        query = db.query(Webinar)
    
    if status:
        try:
            query = query.filter(Webinar.status == WebinarStatus(status))
        except ValueError:
            pass
    
    query = query.filter(Webinar.date >= start_date)
    
    total = query.count()
    webinars = query.order_by(Webinar.date.desc()).offset(skip).limit(limit).all()
    
    webinar_ids = [w.webinar_id for w in webinars]
    
    # Batch query for attendance stats
    attendance_stats = {}
    if webinar_ids:
        stats = db.query(
            StudentWebinarAttendance.webinar_id,
            func.count(StudentWebinarAttendance.id).label('total_invited'),
            func.sum(case((StudentWebinarAttendance.attended == True, 1), else_=0)).label('attended'),
            func.avg(StudentWebinarAttendance.watch_duration_minutes).label('avg_watch_time')
        ).filter(
            StudentWebinarAttendance.webinar_id.in_(webinar_ids)
        ).group_by(StudentWebinarAttendance.webinar_id).all()
        
        attendance_stats = {s.webinar_id: s for s in stats}
    
    result = []
    for w in webinars:
        stats = attendance_stats.get(w.webinar_id)
        total_invited = stats.total_invited if stats else 0
        attended = stats.attended if stats else 0
        
        result.append({
            "webinar_id": w.webinar_id,
            "title": w.title,
            "description": w.description,
            "school_id": w.school_id,
            "class_ids": w.class_ids,
            "target_audience": w.target_audience.value if w.target_audience else None,
            "target_grades": w.target_grades,
            "speaker_name": w.speaker_name,
            "date": w.date,
            "duration_minutes": w.duration_minutes,
            "category": w.category.value if w.category else None,
            "status": w.status.value if w.status else None,
            "thumbnail_url": w.thumbnail_url,
            "analytics": {
                "total_invited": total_invited,
                "total_attended": attended,
                "attendance_rate": round(attended / total_invited * 100, 1) if total_invited > 0 else 0,
                "avg_watch_time": round(stats.avg_watch_time, 1) if stats and stats.avg_watch_time else 0
            }
        })
    
    return success_response({
        "total": total,
        "skip": skip,
        "limit": limit,
        "webinars": result
    })


# ============== SCHOOL REGISTRATIONS (must be before /{webinar_id}) ==============

@router.get("/registrations")
async def get_my_registrations(
    school_id: UUID,
    status: Optional[str] = None,
    include_analytics: bool = False,
    db: Session = Depends(get_db)
):
    """Get all webinars registered by the school."""
    query = db.query(WebinarSchoolRegistration).options(
        joinedload(WebinarSchoolRegistration.webinar)
    ).filter(WebinarSchoolRegistration.school_id == school_id)
    
    if status:
        try:
            query = query.filter(WebinarSchoolRegistration.status == RegistrationStatus(status))
        except ValueError:
            pass
    
    registrations = query.order_by(WebinarSchoolRegistration.created_at.desc()).all()
    
    # Get class names for all registrations
    all_class_ids = []
    for reg in registrations:
        if reg.class_ids:
            all_class_ids.extend(reg.class_ids)
    
    class_names = {}
    if all_class_ids:
        classes = db.query(Class.class_id, Class.name).filter(Class.class_id.in_(all_class_ids)).all()
        class_names = {c.class_id: c.name for c in classes}
    
    result = []
    for reg in registrations:
        webinar = reg.webinar
        
        item = {
            "registration_id": reg.id,
            "webinar_id": reg.webinar_id,
            "webinar": {
                "title": webinar.title if webinar else None,
                "speaker_name": webinar.speaker_name if webinar else None,
                "date": webinar.date if webinar else None,
                "duration_minutes": webinar.duration_minutes if webinar else None,
                "status": webinar.status.value if webinar and webinar.status else None,
                "category": webinar.category.value if webinar and webinar.category else None,
                "thumbnail_url": webinar.thumbnail_url if webinar else None
            },
            "registration_type": reg.registration_type.value,
            "class_ids": reg.class_ids,
            "class_names": [class_names.get(cid) for cid in (reg.class_ids or []) if class_names.get(cid)],
            "total_students_invited": reg.total_students_invited,
            "registered_at": reg.created_at,
            "analytics": None
        }
        
        if include_analytics:
            # Get attendance stats
            stats = db.query(
                func.sum(case((StudentWebinarAttendance.attended == True, 1), else_=0)).label('attended'),
                func.avg(StudentWebinarAttendance.watch_duration_minutes).label('avg_watch_time')
            ).filter(StudentWebinarAttendance.webinar_id == reg.webinar_id).first()
            
            attended = stats.attended or 0
            item["analytics"] = {
                "total_attended": attended,
                "attendance_rate": round(attended / reg.total_students_invited * 100, 1) if reg.total_students_invited > 0 else 0,
                "avg_watch_time": round(stats.avg_watch_time, 1) if stats.avg_watch_time else 0
            }
        
        result.append(item)
    
    return success_response({
        "total_registrations": len(result),
        "registrations": result
    })


@router.get("/registered")
async def get_registered_webinar_analytics(
    school_id: UUID,
    status: Optional[str] = None,
    days: int = Query(30, description="Filter to last N days"),
    db: Session = Depends(get_db)
):
    """Get analytics only for webinars that the school has registered for."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get registrations
    query = db.query(WebinarSchoolRegistration).options(
        joinedload(WebinarSchoolRegistration.webinar)
    ).filter(
        WebinarSchoolRegistration.school_id == school_id,
        WebinarSchoolRegistration.created_at >= start_date
    )
    
    if status:
        try:
            query = query.filter(WebinarSchoolRegistration.status == RegistrationStatus(status))
        except ValueError:
            pass
    
    registrations = query.all()
    
    if not registrations:
        return success_response({
            "school_id": school_id,
            "total_registered_webinars": 0,
            "summary": {
                "total_students_invited": 0,
                "total_attended": 0,
                "overall_attendance_rate": 0,
                "avg_watch_time": 0
            },
            "webinars": []
        })
    
    webinar_ids = [r.webinar_id for r in registrations]
    
    # Get class names
    all_class_ids = []
    for reg in registrations:
        if reg.class_ids:
            all_class_ids.extend(reg.class_ids)
    
    class_names = {}
    if all_class_ids:
        classes = db.query(Class.class_id, Class.name).filter(Class.class_id.in_(all_class_ids)).all()
        class_names = {c.class_id: c.name for c in classes}
    
    # Get attendance stats per webinar
    attendance_stats = {}
    stats = db.query(
        StudentWebinarAttendance.webinar_id,
        func.count(StudentWebinarAttendance.id).label('total_invited'),
        func.sum(case((StudentWebinarAttendance.attended == True, 1), else_=0)).label('attended'),
        func.avg(StudentWebinarAttendance.watch_duration_minutes).label('avg_watch_time')
    ).filter(
        StudentWebinarAttendance.webinar_id.in_(webinar_ids)
    ).group_by(StudentWebinarAttendance.webinar_id).all()
    
    attendance_stats = {s.webinar_id: s for s in stats}
    
    # Build response
    total_invited = 0
    total_attended = 0
    total_watch_time = 0
    watch_count = 0
    
    webinars_data = []
    for reg in registrations:
        webinar = reg.webinar
        stats = attendance_stats.get(reg.webinar_id)
        
        invited = stats.total_invited if stats else reg.total_students_invited
        attended = stats.attended if stats else 0
        avg_watch = stats.avg_watch_time if stats else 0
        
        total_invited += invited
        total_attended += attended
        if avg_watch:
            total_watch_time += avg_watch
            watch_count += 1
        
        webinars_data.append({
            "webinar_id": reg.webinar_id,
            "title": webinar.title if webinar else None,
            "speaker_name": webinar.speaker_name if webinar else None,
            "date": webinar.date if webinar else None,
            "status": webinar.status.value if webinar and webinar.status else None,
            "registration_type": reg.registration_type.value,
            "classes_registered": [class_names.get(cid) for cid in (reg.class_ids or []) if class_names.get(cid)],
            "analytics": {
                "total_invited": invited,
                "total_attended": attended,
                "attendance_rate": round(attended / invited * 100, 1) if invited > 0 else 0,
                "avg_watch_time": round(avg_watch, 1) if avg_watch else 0
            }
        })
    
    return success_response({
        "school_id": school_id,
        "total_registered_webinars": len(registrations),
        "summary": {
            "total_students_invited": total_invited,
            "total_attended": total_attended,
            "overall_attendance_rate": round(total_attended / total_invited * 100, 1) if total_invited > 0 else 0,
            "avg_watch_time": round(total_watch_time / watch_count, 1) if watch_count > 0 else 0
        },
        "webinars": webinars_data
    })


# ============== 2. SINGLE WEBINAR ANALYTICS ==============

@router.get("/{webinar_id}")
async def get_webinar_analytics(
    webinar_id: UUID,
    db: Session = Depends(get_db)
):
    """Get detailed analytics for a single webinar."""
    webinar = db.query(Webinar).filter(Webinar.webinar_id == webinar_id).first()
    if not webinar:
        raise HTTPException(status_code=404, detail="Webinar not found")
    
    # Get attendance stats
    stats = db.query(
        func.count(StudentWebinarAttendance.id).label('total_invited'),
        func.sum(case((StudentWebinarAttendance.attended == True, 1), else_=0)).label('attended'),
        func.avg(StudentWebinarAttendance.watch_duration_minutes).label('avg_watch_time'),
        func.min(StudentWebinarAttendance.watch_duration_minutes).label('min_watch_time'),
        func.max(StudentWebinarAttendance.watch_duration_minutes).label('max_watch_time')
    ).filter(StudentWebinarAttendance.webinar_id == webinar_id).first()
    
    total_invited = stats.total_invited or 0
    attended = stats.attended or 0
    
    # Attendance by class
    class_breakdown = []
    if webinar.class_ids:
        for class_id in webinar.class_ids:
            cls = db.query(Class).filter(Class.class_id == class_id).first()
            if cls:
                class_stats = db.query(
                    func.count(StudentWebinarAttendance.id).label('invited'),
                    func.sum(case((StudentWebinarAttendance.attended == True, 1), else_=0)).label('attended')
                ).join(Student, StudentWebinarAttendance.student_id == Student.student_id).filter(
                    StudentWebinarAttendance.webinar_id == webinar_id,
                    Student.class_id == class_id
                ).first()
                
                class_breakdown.append({
                    "class_id": class_id,
                    "class_name": cls.name,
                    "grade": cls.grade,
                    "invited": class_stats.invited or 0,
                    "attended": class_stats.attended or 0,
                    "attendance_rate": round((class_stats.attended or 0) / (class_stats.invited or 1) * 100, 1)
                })
    
    # Watch time distribution
    watch_distribution = {"0-25%": 0, "25-50%": 0, "50-75%": 0, "75-100%": 0}
    if webinar.duration_minutes and attended > 0:
        attendances = db.query(StudentWebinarAttendance.watch_duration_minutes).filter(
            StudentWebinarAttendance.webinar_id == webinar_id,
            StudentWebinarAttendance.attended == True
        ).all()
        
        for att in attendances:
            if att.watch_duration_minutes:
                pct = att.watch_duration_minutes / webinar.duration_minutes
                if pct < 0.25:
                    watch_distribution["0-25%"] += 1
                elif pct < 0.5:
                    watch_distribution["25-50%"] += 1
                elif pct < 0.75:
                    watch_distribution["50-75%"] += 1
                else:
                    watch_distribution["75-100%"] += 1
    
    return success_response({
        "webinar_id": webinar_id,
        "title": webinar.title,
        "description": webinar.description,
        "school_id": webinar.school_id,
        "class_ids": webinar.class_ids,
        "target_audience": webinar.target_audience.value if webinar.target_audience else None,
        "target_grades": webinar.target_grades,
        "speaker": {
            "name": webinar.speaker_name,
            "title": webinar.speaker_title,
            "bio": webinar.speaker_bio,
            "image_url": webinar.speaker_image_url
        },
        "schedule": {
            "date": webinar.date,
            "duration_minutes": webinar.duration_minutes,
            "status": webinar.status.value if webinar.status else None
        },
        "category": webinar.category.value if webinar.category else None,
        "analytics": {
            "total_invited": total_invited,
            "total_attended": attended,
            "total_absent": total_invited - attended,
            "attendance_rate": round(attended / total_invited * 100, 1) if total_invited > 0 else 0,
            "avg_watch_time": round(stats.avg_watch_time, 1) if stats.avg_watch_time else 0,
            "min_watch_time": stats.min_watch_time or 0,
            "max_watch_time": stats.max_watch_time or 0,
            "completion_rate": round((stats.avg_watch_time or 0) / webinar.duration_minutes * 100, 1) if webinar.duration_minutes else 0
        },
        "class_breakdown": class_breakdown,
        "watch_time_distribution": watch_distribution
    })


# ============== 3. WEBINAR PARTICIPANTS ==============

@router.get("/{webinar_id}/participants")
async def get_webinar_participants(
    webinar_id: UUID,
    attended: Optional[bool] = None,
    class_id: Optional[UUID] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get participant list for a webinar with attendance details."""
    webinar = db.query(Webinar).filter(Webinar.webinar_id == webinar_id).first()
    if not webinar:
        raise HTTPException(status_code=404, detail="Webinar not found")
    
    query = db.query(StudentWebinarAttendance).options(
        joinedload(StudentWebinarAttendance.student)
    ).filter(StudentWebinarAttendance.webinar_id == webinar_id)
    
    if attended is not None:
        query = query.filter(StudentWebinarAttendance.attended == attended)
    
    if class_id:
        query = query.join(Student).filter(Student.class_id == class_id)
    
    if search:
        query = query.join(Student).filter(or_(
            Student.first_name.ilike(f"%{search}%"),
            Student.last_name.ilike(f"%{search}%")
        ))
    
    total = query.count()
    attendances = query.offset(skip).limit(limit).all()
    
    # Get class names
    student_ids = [a.student_id for a in attendances]
    students = db.query(Student).filter(Student.student_id.in_(student_ids)).all()
    student_map = {s.student_id: s for s in students}
    
    class_ids = list(set(s.class_id for s in students if s.class_id))
    class_names = {c.class_id: c.name for c in db.query(Class.class_id, Class.name).filter(Class.class_id.in_(class_ids)).all()} if class_ids else {}
    
    participants = []
    for att in attendances:
        student = student_map.get(att.student_id)
        if student:
            watch_pct = round(att.watch_duration_minutes / webinar.duration_minutes * 100, 1) if att.watch_duration_minutes and webinar.duration_minutes else 0
            
            participants.append({
                "student_id": att.student_id,
                "student_name": f"{student.first_name} {student.last_name}",
                "class_id": student.class_id,
                "class_name": class_names.get(student.class_id),
                "grade": student.grade,
                "attended": att.attended,
                "join_time": att.join_time,
                "leave_time": att.leave_time,
                "watch_duration_minutes": att.watch_duration_minutes,
                "watch_percentage": watch_pct,
                "status": "Completed" if watch_pct >= 75 else ("Partial" if watch_pct > 0 else "Absent")
            })
    
    return success_response({
        "webinar_id": webinar_id,
        "title": webinar.title,
        "total_participants": total,
        "skip": skip,
        "limit": limit,
        "participants": participants
    })


# ============== 4. ASSIGN WEBINAR TO CLASSES ==============

@router.post("/{webinar_id}/assign")
async def assign_webinar_to_classes(
    webinar_id: UUID,
    school_id: UUID,
    class_ids: Optional[List[UUID]] = None,
    grades: Optional[List[str]] = None,
    db: Session = Depends(get_db)
):
    """
    Assign a webinar to specific classes or grades.
    Creates attendance records for all students in the target classes.
    """
    webinar = db.query(Webinar).filter(Webinar.webinar_id == webinar_id).first()
    if not webinar:
        raise HTTPException(status_code=404, detail="Webinar not found")
    
    # Update webinar assignment
    webinar.school_id = school_id
    webinar.class_ids = class_ids
    webinar.target_grades = grades
    
    # Get target students
    student_query = db.query(Student).filter(Student.school_id == school_id)
    
    if class_ids:
        student_query = student_query.filter(Student.class_id.in_(class_ids))
    elif grades:
        student_query = student_query.filter(Student.grade.in_(grades))
    
    students = student_query.all()
    
    # Create attendance records (skip existing)
    existing = set(
        a.student_id for a in db.query(StudentWebinarAttendance.student_id).filter(
            StudentWebinarAttendance.webinar_id == webinar_id
        ).all()
    )
    
    created = 0
    for student in students:
        if student.student_id not in existing:
            db.add(StudentWebinarAttendance(
                webinar_id=webinar_id,
                student_id=student.student_id,
                attended=False
            ))
            created += 1
    
    db.commit()
    
    return success_response({
        "webinar_id": webinar_id,
        "school_id": school_id,
        "class_ids": class_ids,
        "target_grades": grades,
        "total_students_assigned": len(students),
        "new_records_created": created,
        "existing_records": len(existing)
    })


# ============== 5. SCHOOL WEBINAR SUMMARY ==============

@router.get("/school/{school_id}/summary")
async def get_school_webinar_summary(
    school_id: UUID,
    days: int = Query(30, description="Filter to last N days"),
    db: Session = Depends(get_db)
):
    """Get webinar summary for a school."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get webinars for this school
    webinars = db.query(Webinar).filter(
        or_(Webinar.school_id == school_id, Webinar.school_id.is_(None)),
        Webinar.date >= start_date
    ).all()
    
    webinar_ids = [w.webinar_id for w in webinars]
    
    if not webinar_ids:
        return success_response({
            "school_id": school_id,
            "period_days": days,
            "total_webinars": 0,
            "summary": {}
        })
    
    # Get student IDs for this school
    student_ids = [s[0] for s in db.query(Student.student_id).filter(Student.school_id == school_id).all()]
    
    # Overall stats
    stats = db.query(
        func.count(StudentWebinarAttendance.id).label('total_invites'),
        func.sum(case((StudentWebinarAttendance.attended == True, 1), else_=0)).label('total_attended'),
        func.avg(StudentWebinarAttendance.watch_duration_minutes).label('avg_watch_time')
    ).filter(
        StudentWebinarAttendance.webinar_id.in_(webinar_ids),
        StudentWebinarAttendance.student_id.in_(student_ids)
    ).first()
    
    # By status
    status_counts = {}
    for w in webinars:
        status = w.status.value if w.status else "Unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # By category
    category_counts = {}
    for w in webinars:
        cat = w.category.value if w.category else "Other"
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    total_invites = stats.total_invites or 0
    total_attended = stats.total_attended or 0
    
    return success_response({
        "school_id": school_id,
        "period_days": days,
        "total_webinars": len(webinars),
        "summary": {
            "total_student_invites": total_invites,
            "total_attended": total_attended,
            "overall_attendance_rate": round(total_attended / total_invites * 100, 1) if total_invites > 0 else 0,
            "avg_watch_time": round(stats.avg_watch_time, 1) if stats.avg_watch_time else 0
        },
        "by_status": status_counts,
        "by_category": category_counts,
        "upcoming": len([w for w in webinars if w.status == WebinarStatus.UPCOMING]),
        "completed": len([w for w in webinars if w.status == WebinarStatus.RECORDED])
    })



# ============== SCHEMAS ==============

class WebinarRegistrationRequest(BaseModel):
    registration_type: str = "school"  # "school" or "class"
    class_ids: Optional[List[UUID]] = None
    grade_ids: Optional[List[str]] = None
    notify_students: bool = True


# ============== 6. REGISTER WEBINAR ==============

@router.post("/{webinar_id}/register")
async def register_webinar(
    webinar_id: UUID,
    school_id: UUID,
    request: WebinarRegistrationRequest,
    user_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    """
    Register a webinar for the school with optional class/grade targeting.
    Creates attendance records for all targeted students.
    """
    # Validate webinar
    webinar = db.query(Webinar).filter(Webinar.webinar_id == webinar_id).first()
    if not webinar:
        raise HTTPException(status_code=404, detail="WEBINAR_NOT_FOUND")
    
    if webinar.status == WebinarStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="WEBINAR_CANCELLED")
    
    if webinar.status == WebinarStatus.RECORDED:
        # Allow registration for recorded webinars (on-demand viewing)
        pass
    
    # Check if already registered
    existing = db.query(WebinarSchoolRegistration).filter(
        WebinarSchoolRegistration.webinar_id == webinar_id,
        WebinarSchoolRegistration.school_id == school_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="ALREADY_REGISTERED")
    
    # Validate class_ids if provided
    if request.class_ids:
        valid_classes = db.query(Class.class_id).filter(
            Class.class_id.in_(request.class_ids),
            Class.school_id == school_id
        ).all()
        valid_class_ids = [c[0] for c in valid_classes]
        if len(valid_class_ids) != len(request.class_ids):
            raise HTTPException(status_code=400, detail="INVALID_CLASS_IDS")
    
    # Determine registration type
    reg_type = RegistrationType.CLASS if request.registration_type == "class" else RegistrationType.SCHOOL
    
    # Get target students
    student_query = db.query(Student).filter(Student.school_id == school_id)
    
    if reg_type == RegistrationType.CLASS:
        if request.class_ids:
            student_query = student_query.filter(Student.class_id.in_(request.class_ids))
        if request.grade_ids:
            student_query = student_query.filter(Student.grade.in_(request.grade_ids))
    
    students = student_query.all()
    
    if not students:
        raise HTTPException(status_code=400, detail="NO_STUDENTS_FOUND")
    
    # Create registration
    registration = WebinarSchoolRegistration(
        webinar_id=webinar_id,
        school_id=school_id,
        registration_type=reg_type,
        class_ids=request.class_ids or [],
        grade_ids=request.grade_ids or [],
        registered_by=user_id,
        status=RegistrationStatus.ACTIVE,
        total_students_invited=len(students)
    )
    db.add(registration)
    db.flush()  # Get the registration ID
    
    # Get existing attendance records to avoid duplicates
    existing_attendance = set(
        a.student_id for a in db.query(StudentWebinarAttendance.student_id).filter(
            StudentWebinarAttendance.webinar_id == webinar_id
        ).all()
    )
    
    # Create attendance records for students (skip existing)
    new_records = 0
    for student in students:
        if student.student_id not in existing_attendance:
            db.add(StudentWebinarAttendance(
                webinar_id=webinar_id,
                student_id=student.student_id,
                attended=False
            ))
            new_records += 1
    
    db.commit()
    db.refresh(registration)
    
    return success_response({
        "registration_id": registration.id,
        "webinar_id": webinar_id,
        "school_id": school_id,
        "registration_type": registration.registration_type.value,
        "class_ids": registration.class_ids,
        "grade_ids": registration.grade_ids,
        "total_students_invited": registration.total_students_invited,
        "registered_by": user_id,
        "registered_at": registration.created_at,
        "status": registration.status.value
    })



# ============== 7. WEBINAR CLASS BREAKDOWN ==============

@router.get("/{webinar_id}/class-breakdown")
async def get_webinar_class_breakdown(
    webinar_id: UUID,
    school_id: UUID,
    db: Session = Depends(get_db)
):
    """Get detailed attendance breakdown by class for a registered webinar."""
    webinar = db.query(Webinar).filter(Webinar.webinar_id == webinar_id).first()
    if not webinar:
        raise HTTPException(status_code=404, detail="Webinar not found")
    
    # Check registration
    registration = db.query(WebinarSchoolRegistration).filter(
        WebinarSchoolRegistration.webinar_id == webinar_id,
        WebinarSchoolRegistration.school_id == school_id
    ).first()
    
    if not registration:
        raise HTTPException(status_code=404, detail="NOT_REGISTERED")
    
    # Get all classes with students who have attendance records
    student_ids = [a.student_id for a in db.query(StudentWebinarAttendance.student_id).filter(
        StudentWebinarAttendance.webinar_id == webinar_id
    ).all()]
    
    if not student_ids:
        return success_response({
            "webinar_id": webinar_id,
            "title": webinar.title,
            "total_classes": 0,
            "class_breakdown": []
        })
    
    # Get students with their classes
    students = db.query(Student).filter(
        Student.student_id.in_(student_ids),
        Student.school_id == school_id
    ).all()
    
    # Group by class
    class_students = {}
    for s in students:
        if s.class_id not in class_students:
            class_students[s.class_id] = []
        class_students[s.class_id].append(s)
    
    # Get class info
    class_ids = list(class_students.keys())
    classes = db.query(Class).filter(Class.class_id.in_(class_ids)).all()
    class_map = {c.class_id: c for c in classes}
    
    # Get teacher names
    teacher_ids = [c.teacher_id for c in classes if c.teacher_id]
    teacher_names = {}
    if teacher_ids:
        teachers = db.query(User.user_id, User.display_name).filter(User.user_id.in_(teacher_ids)).all()
        teacher_names = {t.user_id: t.display_name for t in teachers}
    
    # Get attendance data
    attendance_map = {a.student_id: a for a in db.query(StudentWebinarAttendance).filter(
        StudentWebinarAttendance.webinar_id == webinar_id,
        StudentWebinarAttendance.student_id.in_(student_ids)
    ).all()}
    
    class_breakdown = []
    for class_id, class_student_list in class_students.items():
        cls = class_map.get(class_id)
        if not cls:
            continue
        
        attended_count = 0
        total_watch_time = 0
        completed_count = 0
        student_details = []
        
        for student in class_student_list:
            att = attendance_map.get(student.student_id)
            if att:
                watch_pct = round(att.watch_duration_minutes / webinar.duration_minutes * 100, 1) if att.watch_duration_minutes and webinar.duration_minutes else 0
                
                if att.attended:
                    attended_count += 1
                    total_watch_time += att.watch_duration_minutes or 0
                    if watch_pct >= 75:
                        completed_count += 1
                
                student_details.append({
                    "student_id": student.student_id,
                    "student_name": f"{student.first_name} {student.last_name}",
                    "attended": att.attended,
                    "watch_duration_minutes": att.watch_duration_minutes,
                    "watch_percentage": watch_pct,
                    "status": "Completed" if watch_pct >= 75 else ("Partial" if watch_pct > 0 else "Absent")
                })
        
        total_students = len(class_student_list)
        class_breakdown.append({
            "class_id": class_id,
            "class_name": cls.name,
            "grade": cls.grade,
            "section": cls.section,
            "teacher_name": teacher_names.get(cls.teacher_id),
            "total_students": total_students,
            "invited": total_students,
            "attended": attended_count,
            "attendance_rate": round(attended_count / total_students * 100, 1) if total_students > 0 else 0,
            "avg_watch_time": round(total_watch_time / attended_count, 1) if attended_count > 0 else 0,
            "completion_rate": round(completed_count / total_students * 100, 1) if total_students > 0 else 0,
            "students": student_details
        })
    
    return success_response({
        "webinar_id": webinar_id,
        "title": webinar.title,
        "total_classes": len(class_breakdown),
        "class_breakdown": class_breakdown
    })



# ============== 10. UNREGISTER WEBINAR ==============

@router.post("/{webinar_id}/unregister")
async def unregister_webinar(
    webinar_id: UUID,
    school_id: UUID,
    db: Session = Depends(get_db)
):
    """Unregister a webinar and remove all student invitations."""
    # Check registration exists
    registration = db.query(WebinarSchoolRegistration).filter(
        WebinarSchoolRegistration.webinar_id == webinar_id,
        WebinarSchoolRegistration.school_id == school_id
    ).first()
    
    if not registration:
        raise HTTPException(status_code=404, detail="NOT_REGISTERED")
    
    # Get student IDs for this school
    student_ids = [s[0] for s in db.query(Student.student_id).filter(Student.school_id == school_id).all()]
    
    # Delete attendance records
    deleted = db.query(StudentWebinarAttendance).filter(
        StudentWebinarAttendance.webinar_id == webinar_id,
        StudentWebinarAttendance.student_id.in_(student_ids)
    ).delete(synchronize_session=False)
    
    # Delete registration
    db.delete(registration)
    db.commit()
    
    return success_response({
        "webinar_id": webinar_id,
        "school_id": school_id,
        "students_removed": deleted,
        "unregistered_at": datetime.utcnow()
    })


# ============== 11. ENHANCED ASSIGN WEBINAR ==============

@router.post("/{webinar_id}/assign-enhanced")
async def assign_webinar_enhanced(
    webinar_id: UUID,
    school_id: UUID,
    assignment_type: str = Query(..., description="'school' or 'class'"),
    class_ids: Optional[List[UUID]] = Query(None),
    grades: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Enhanced webinar assignment with registration tracking.
    Creates both registration record and attendance records.
    """
    webinar = db.query(Webinar).filter(Webinar.webinar_id == webinar_id).first()
    if not webinar:
        raise HTTPException(status_code=404, detail="Webinar not found")
    
    # Check if already registered
    existing = db.query(WebinarSchoolRegistration).filter(
        WebinarSchoolRegistration.webinar_id == webinar_id,
        WebinarSchoolRegistration.school_id == school_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="ALREADY_REGISTERED")
    
    # Validate class_ids
    valid_class_ids = []
    if class_ids:
        valid_classes = db.query(Class).filter(
            Class.class_id.in_(class_ids),
            Class.school_id == school_id
        ).all()
        valid_class_ids = [c.class_id for c in valid_classes]
    
    # Get target students
    student_query = db.query(Student).filter(Student.school_id == school_id)
    
    if assignment_type == "class":
        if valid_class_ids:
            student_query = student_query.filter(Student.class_id.in_(valid_class_ids))
        if grades:
            student_query = student_query.filter(Student.grade.in_(grades))
    
    students = student_query.all()
    
    if not students:
        raise HTTPException(status_code=400, detail="NO_STUDENTS_FOUND")
    
    # Create registration
    reg_type = RegistrationType.CLASS if assignment_type == "class" else RegistrationType.SCHOOL
    registration = WebinarSchoolRegistration(
        webinar_id=webinar_id,
        school_id=school_id,
        registration_type=reg_type,
        class_ids=valid_class_ids or [],
        grade_ids=grades or [],
        status=RegistrationStatus.ACTIVE,
        total_students_invited=len(students)
    )
    db.add(registration)
    
    # Create attendance records
    existing_student_ids = set(
        a.student_id for a in db.query(StudentWebinarAttendance.student_id).filter(
            StudentWebinarAttendance.webinar_id == webinar_id
        ).all()
    )
    
    new_records = 0
    for student in students:
        if student.student_id not in existing_student_ids:
            db.add(StudentWebinarAttendance(
                webinar_id=webinar_id,
                student_id=student.student_id,
                attended=False
            ))
            new_records += 1
    
    db.commit()
    
    # Get class breakdown
    class_breakdown = []
    if valid_class_ids:
        for class_id in valid_class_ids:
            cls = db.query(Class).filter(Class.class_id == class_id).first()
            count = len([s for s in students if s.class_id == class_id])
            if cls:
                class_breakdown.append({
                    "class_id": class_id,
                    "class_name": cls.name,
                    "students_count": count
                })
    
    return success_response({
        "webinar_id": webinar_id,
        "school_id": school_id,
        "assignment_type": assignment_type,
        "class_ids": valid_class_ids,
        "grades": grades,
        "total_students_assigned": len(students),
        "new_records_created": new_records,
        "existing_records": len(existing_student_ids),
        "classes_assigned": class_breakdown
    })
