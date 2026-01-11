from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from uuid import UUID
from app.core.database import get_db
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.models.case import Case, JournalEntry
from app.models.user import User, UserRole
from app.models.class_model import Class
from app.schemas.case import CaseCreate, CaseUpdate, CaseResponse, CaseDetailResponse, JournalEntryCreate, JournalEntryResponse

# Initialize logger
logger = get_logger(__name__)

router = APIRouter()

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_case(case_data: CaseCreate, db: Session = Depends(get_db)):
    logger.info(
        f"Creating case for student: {case_data.student_id}",
        extra={"extra_data": {"student_id": str(case_data.student_id), "created_by": str(case_data.created_by), "risk_level": str(case_data.initial_risk)}}
    )
    
    case = Case(
        student_id=case_data.student_id,
        created_by=case_data.created_by,
        risk_level=case_data.initial_risk,
        ai_summary=case_data.presenting_concerns
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    
    logger.info(
        f"Case created successfully",
        extra={"extra_data": {"case_id": str(case.case_id), "student_id": str(case.student_id), "risk_level": str(case.risk_level)}}
    )
    return success_response(case)

@router.get("/{case_id}")
async def get_case(case_id: UUID, db: Session = Depends(get_db)):
    logger.debug(f"Fetching case: {case_id}")
    
    # Fetch case with related student (User model)
    case = (
        db.query(Case)
        .options(joinedload(Case.student))
        .filter(Case.case_id == case_id)
        .first()
    )

    if not case:
        logger.warning(f"Case not found: {case_id}")
        raise HTTPException(status_code=404, detail="Case not found")

    # Fetch counsellor data if assigned
    counsellor = None
    if case.assigned_counsellor:
        counsellor = (
            db.query(User)
            .filter(User.user_id == case.assigned_counsellor, User.role == UserRole.COUNSELLOR)
            .first()
        )

    # Build response data
    response_data = {
        "case": case,
        "student": {
            "student_id": case.student.user_id if case.student else None,
            "first_name": case.student.display_name.split()[0] if case.student and case.student.display_name else None,
            "last_name": " ".join(case.student.display_name.split()[1:]) if case.student and case.student.display_name and len(case.student.display_name.split()) > 1 else None,
            "display_name": case.student.display_name if case.student else None,
            "email": case.student.email if case.student else None,
            "school_id": case.student.school_id if case.student else None,
        },
        "counsellor": None,
    }

    # Add counsellor data if exists
    if counsellor:
        response_data["counsellor"] = {
            "user_id": counsellor.user_id,
            "display_name": counsellor.display_name,
            "email": counsellor.email,
            "phone": counsellor.phone
        }

    return success_response(response_data)

@router.get("")
async def list_cases(school_id: UUID = None, student_id: UUID = None, status: str = None, risk_level: str = None, assigned_counsellor: UUID = None, teacher_id: UUID = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.debug(
        "Listing cases",
        extra={"extra_data": {"school_id": str(school_id) if school_id else None, "student_id": str(student_id) if student_id else None, "status": status, "risk_level": risk_level, "teacher_id": str(teacher_id) if teacher_id else None}}
    )
    
    # Build base query with joined load for student (User model)
    query = (
        db.query(Case)
        .options(joinedload(Case.student))
    )

    if school_id:
        query = query.join(Case.student).filter(User.school_id == school_id)
    if student_id:
        query = query.filter(Case.student_id == student_id)
    if status:
        query = query.filter(Case.status == status)
    if risk_level:
        query = query.filter(Case.risk_level == risk_level)
    if assigned_counsellor:
        query = query.filter(Case.assigned_counsellor == assigned_counsellor)
    
    # Filter by teacher's classes if teacher_id is provided
    if teacher_id:
        # Get class IDs for this teacher
        teacher_class_ids = db.query(Class.class_id).filter(Class.teacher_id == teacher_id).all()
        teacher_class_ids = [str(c[0]) for c in teacher_class_ids]
        if teacher_class_ids:
            # Get student IDs from teacher's classes
            student_ids_in_teacher_classes = db.query(User.user_id).filter(
                User.profile["class_id"].astext.in_(teacher_class_ids)
            ).all()
            student_ids = [s[0] for s in student_ids_in_teacher_classes]
            if student_ids:
                query = query.filter(Case.student_id.in_(student_ids))
            else:
                return success_response([])
        else:
            # Teacher has no classes, return empty
            return success_response([])

    cases = query.offset(skip).limit(limit).all()
    logger.debug(f"Found {len(cases)} cases")

    # Get all counsellor IDs to fetch in batch
    counsellor_ids = [case.assigned_counsellor for case in cases if case.assigned_counsellor]

    # Fetch counsellors in batch
    counsellors = {}
    if counsellor_ids:
        counsellor_results = (
            db.query(User)
            .filter(User.user_id.in_(counsellor_ids), User.role == UserRole.COUNSELLOR)
            .all()
        )
        counsellors = {c.user_id: c for c in counsellor_results}

    # Get all class IDs from students to fetch teachers
    class_ids = []
    for case in cases:
        if case.student and case.student.profile and case.student.profile.get("class_id"):
            class_ids.append(case.student.profile.get("class_id"))
    
    # Fetch classes with teachers in batch
    teachers_by_class = {}
    if class_ids:
        classes_with_teachers = (
            db.query(Class)
            .options(joinedload(Class.teacher))
            .filter(Class.class_id.in_(class_ids))
            .all()
        )
        for cls in classes_with_teachers:
            if cls.teacher:
                teachers_by_class[str(cls.class_id)] = cls.teacher

    # Build response data for each case
    result = []
    for case in cases:
        counsellor = counsellors.get(case.assigned_counsellor) if case.assigned_counsellor else None
        
        # Get teacher for this student's class
        teacher = None
        if case.student and case.student.profile and case.student.profile.get("class_id"):
            teacher = teachers_by_class.get(case.student.profile.get("class_id"))

        case_data = {
            "case": case,
            "student": {
                "student_id": case.student.user_id if case.student else None,
                "first_name": case.student.display_name.split()[0] if case.student and case.student.display_name else None,
                "last_name": " ".join(case.student.display_name.split()[1:]) if case.student and case.student.display_name and len(case.student.display_name.split()) > 1 else None,
                "display_name": case.student.display_name if case.student else None,
                "email": case.student.email if case.student else None,
                "school_id": case.student.school_id if case.student else None,
                "class_id": case.student.profile.get("class_id") if case.student and case.student.profile else None,
            },
            "counsellor": None,
            "teacher": None,
        }

        # Add counsellor data if exists
        if counsellor:
            case_data["counsellor"] = {
                "user_id": counsellor.user_id,
                "display_name": counsellor.display_name,
                "email": counsellor.email,
                "phone": counsellor.phone
            }
        
        # Add teacher data if exists
        if teacher:
            case_data["teacher"] = {
                "user_id": teacher.user_id,
                "display_name": teacher.display_name,
                "email": teacher.email,
                "phone": teacher.phone
            }

        result.append(case_data)

    return success_response(result)

@router.post("/{case_id}/journal", status_code=status.HTTP_201_CREATED)
async def create_journal_entry(case_id: UUID, entry_data: JournalEntryCreate, db: Session = Depends(get_db)):
    logger.info(
        f"Creating journal entry for case: {case_id}",
        extra={"extra_data": {"case_id": str(case_id), "author_id": str(entry_data.author_id), "type": str(entry_data.type)}}
    )
    
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        logger.warning(f"Journal entry creation failed - case not found: {case_id}")
        raise HTTPException(status_code=404, detail="Case not found")

    entry = JournalEntry(
        case_id=case_id,
        author_id=entry_data.author_id,
        visibility=entry_data.visibility,
        type=entry_data.type,
        content=entry_data.content,
        audio_url=entry_data.audio_url
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    logger.info(f"Journal entry created successfully", extra={"extra_data": {"entry_id": str(entry.entry_id), "case_id": str(case_id)}})
    return success_response(entry)

@router.get("/{case_id}/journal")
async def get_journal_entries(case_id: UUID, db: Session = Depends(get_db)):
    # Fetch journal entries with author information
    journal_entries = (
        db.query(JournalEntry)
        .options(joinedload(JournalEntry.author))
        .filter(JournalEntry.case_id == case_id)
        .order_by(JournalEntry.created_at.desc())
        .all()
    )

    # Build response data with author names
    result = []
    for entry in journal_entries:
        entry_data = {
            "entry_id": entry.entry_id,
            "case_id": entry.case_id,
            "author_id": entry.author_id,
            "author_name": entry.author.display_name if entry.author else None,
            "visibility": entry.visibility,
            "type": entry.type,
            "content": entry.content,
            "audio_url": entry.audio_url,
            "created_at": entry.created_at
        }
        result.append(entry_data)

    return success_response(result)

@router.patch("/{case_id}")
async def update_case(case_id: UUID, case_update: CaseUpdate, db: Session = Depends(get_db)):
    """Update case details"""
    logger.info(f"Updating case: {case_id}")
    
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        logger.warning(f"Case update failed - not found: {case_id}")
        raise HTTPException(status_code=404, detail="Case not found")

    # Update fields if provided
    update_data = case_update.dict(exclude_unset=True)
    logger.debug(f"Update fields: {list(update_data.keys())}")
    
    for field, value in update_data.items():
        setattr(case, field, value)

    db.commit()
    db.refresh(case)
    
    logger.info(
        f"Case updated successfully",
        extra={"extra_data": {"case_id": str(case_id), "updated_fields": list(update_data.keys())}}
    )
    return success_response(case)

@router.post("/{case_id}/process")
async def process_case(case_id: UUID, db: Session = Depends(get_db)):
    """Mark a case as processed/reviewed"""
    logger.info(f"Processing case: {case_id}")
    
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        logger.warning(f"Case processing failed - not found: {case_id}")
        raise HTTPException(status_code=404, detail="Case not found")

    case.processed = True
    db.commit()
    db.refresh(case)
    
    logger.info(f"Case processed successfully", extra={"extra_data": {"case_id": str(case_id)}})
    return success_response(case)
