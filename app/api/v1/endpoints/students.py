"""
Students API endpoints.
Students are stored in b2b_users table with role=STUDENT.
Student-specific data is stored in the profile JSON column.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import uuid as uuid_module
from app.core.database import get_db
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.core.security import get_password_hash
from app.core.student_helpers import (
    get_student_by_id, get_students_by_school, 
    user_to_student_dict, get_student_first_name, get_student_last_name
)
from app.models.school import School
from app.models.class_model import Class
from app.models.user import User, UserRole
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate

# Initialize logger
logger = get_logger(__name__)

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_student(student_data: StudentCreate, db: Session = Depends(get_db)):
    logger.info(
        f"Creating student: {student_data.first_name} {student_data.last_name}",
        extra={"extra_data": {"school_id": str(student_data.school_id), "class_id": str(student_data.class_id) if student_data.class_id else None}}
    )
    
    # Validate school exists
    school = db.query(School).filter(School.school_id == student_data.school_id).first()
    if not school:
        logger.warning(f"Student creation failed - school not found: {student_data.school_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )

    # Validate class exists if class_id is provided
    if student_data.class_id:
        class_obj = db.query(Class).filter(Class.class_id == student_data.class_id).first()
        if not class_obj:
            logger.warning(f"Student creation failed - class not found: {student_data.class_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )

    # Auto-create parent if parent_email is provided
    created_parent_ids = []
    if student_data.parent_email:
        existing_parent = db.query(User).filter(
            User.email == student_data.parent_email,
            User.school_id == student_data.school_id
        ).first()
        
        if existing_parent and existing_parent.role == UserRole.PARENT:
            created_parent_ids.append(str(existing_parent.user_id))
        elif not existing_parent:
            display_name = student_data.parent_name or student_data.parent_email.split('@')[0].replace('.', ' ').title()
            new_parent = User(
                user_id=uuid_module.uuid4(),
                school_id=student_data.school_id,
                email=student_data.parent_email,
                display_name=display_name,
                phone=student_data.parent_phone,
                role=UserRole.PARENT,
                password_hash=get_password_hash("Welcome123!")
            )
            db.add(new_parent)
            db.flush()
            created_parent_ids.append(str(new_parent.user_id))

    # Validate parents exist if parents_id is provided
    if student_data.parents_id:
        for parent_id in student_data.parents_id:
            parent = db.query(User).filter(User.user_id == parent_id, User.role == UserRole.PARENT).first()
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent with ID {parent_id} not found or is not a parent"
                )
            created_parent_ids.append(str(parent_id))
    
    # Remove duplicates
    created_parent_ids = list(set(created_parent_ids))
    
    # Generate email for student
    email = f"{student_data.first_name.lower()}.{student_data.last_name.lower()}@gmail.com"
    
    # Check if email already exists, append number if needed
    base_email = email
    counter = 2
    while db.query(User).filter(User.email == email).first():
        email = base_email.replace("@gmail.com", f"{counter}@gmail.com")
        counter += 1
    
    # Build profile JSON with student-specific data
    profile = {
        "dob": str(student_data.dob) if student_data.dob else None,
        "gender": student_data.gender.value if student_data.gender else None,
        "class_id": str(student_data.class_id) if student_data.class_id else None,
        "parents_id": created_parent_ids if created_parent_ids else None,
        "parent_email": student_data.parent_email,
        "parent_phone": student_data.parent_phone,
        "migrated_from": "api_create"
    }
    
    # Create student as User with role=STUDENT
    student = User(
        user_id=uuid_module.uuid4(),
        school_id=student_data.school_id,
        role=UserRole.STUDENT,
        email=email,
        display_name=f"{student_data.first_name} {student_data.last_name}",
        phone=student_data.parent_phone,
        profile=profile,
        password_hash=get_password_hash("Welcome123!")
    )
    
    db.add(student)
    db.commit()
    db.refresh(student)
    
    logger.info(
        f"Student created successfully: {student.display_name}",
        extra={"extra_data": {"student_id": str(student.user_id), "school_id": str(student.school_id)}}
    )
    
    return success_response(user_to_student_dict(student))


@router.get("/{student_id}")
async def get_student(student_id: UUID, db: Session = Depends(get_db)):
    logger.debug(f"Fetching student: {student_id}")
    
    student = get_student_by_id(db, student_id)
    if not student:
        logger.warning(f"Student not found: {student_id}")
        raise HTTPException(status_code=404, detail="Student not found")
    
    student_dict = user_to_student_dict(student)
    
    # Get class info if class_id exists
    if student_dict.get("class_id"):
        class_obj = db.query(Class).filter(Class.class_id == student_dict["class_id"]).first()
        if class_obj:
            student_dict["section"] = class_obj.section
            student_dict["class_name"] = class_obj.name
            if not student_dict.get("grade") and class_obj.grade:
                student_dict["grade"] = class_obj.grade
    
    return success_response(student_dict)


@router.get("/")
async def list_students(school_id: UUID, skip: int = 0, limit: int = 300, class_id: UUID = None, db: Session = Depends(get_db)):
    logger.debug(
        f"Listing students for school: {school_id}",
        extra={"extra_data": {"school_id": str(school_id), "class_id": str(class_id) if class_id else None}}
    )
    
    query = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.STUDENT
    )
    
    students = query.offset(skip).limit(limit).all()
    
    # Filter by class_id if provided (stored in profile JSON)
    if class_id:
        students = [s for s in students if s.profile and s.profile.get('class_id') == str(class_id)]
    
    logger.debug(f"Found {len(students)} students")
    
    # Build response
    students_data = []
    for student in students:
        student_dict = user_to_student_dict(student)
        
        # Get class info
        if student_dict.get("class_id"):
            class_obj = db.query(Class).filter(Class.class_id == student_dict["class_id"]).first()
            if class_obj:
                student_dict["section"] = class_obj.section
                student_dict["class_name"] = class_obj.name
                if not student_dict.get("grade") and class_obj.grade:
                    student_dict["grade"] = class_obj.grade
        
        students_data.append(student_dict)
    
    return success_response(students_data)


@router.patch("/{student_id}")
async def update_student(student_id: UUID, student_update: StudentUpdate, db: Session = Depends(get_db)):
    logger.info(f"Updating student: {student_id}")
    
    student = get_student_by_id(db, student_id)
    if not student:
        logger.warning(f"Student update failed - not found: {student_id}")
        raise HTTPException(status_code=404, detail="Student not found")

    update_data = student_update.dict(exclude_unset=True)
    logger.debug(f"Update fields: {list(update_data.keys())}")
    
    # Validate class exists if class_id is being updated
    if "class_id" in update_data and update_data["class_id"] is not None:
        class_obj = db.query(Class).filter(Class.class_id == update_data["class_id"]).first()
        if not class_obj:
            logger.warning(f"Student update failed - class not found: {update_data['class_id']}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )

    # Handle parent creation/update
    created_parent_ids = []
    if "parent_email" in update_data and update_data["parent_email"]:
        existing_parent = db.query(User).filter(
            User.email == update_data["parent_email"],
            User.school_id == student.school_id
        ).first()
        
        if existing_parent and existing_parent.role == UserRole.PARENT:
            created_parent_ids.append(str(existing_parent.user_id))
        elif not existing_parent:
            display_name = update_data.get("parent_name") or update_data["parent_email"].split('@')[0].replace('.', ' ').title()
            new_parent = User(
                user_id=uuid_module.uuid4(),
                school_id=student.school_id,
                email=update_data["parent_email"],
                display_name=display_name,
                phone=update_data.get("parent_phone"),
                role=UserRole.PARENT,
                password_hash=get_password_hash("Welcome123!")
            )
            db.add(new_parent)
            db.flush()
            created_parent_ids.append(str(new_parent.user_id))

    if "parents_id" in update_data and update_data["parents_id"]:
        for parent_id in update_data["parents_id"]:
            parent = db.query(User).filter(User.user_id == parent_id, User.role == UserRole.PARENT).first()
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent with ID {parent_id} not found"
                )
            created_parent_ids.append(str(parent_id))
    elif created_parent_ids:
        # Merge with existing parents
        profile = student.profile or {}
        if profile.get("parents_id"):
            created_parent_ids.extend(profile["parents_id"])
    
    created_parent_ids = list(set(created_parent_ids)) if created_parent_ids else None

    # Update display_name if first_name or last_name changed
    if "first_name" in update_data or "last_name" in update_data:
        current_first = get_student_first_name(student)
        current_last = get_student_last_name(student)
        new_first = update_data.get("first_name", current_first)
        new_last = update_data.get("last_name", current_last)
        student.display_name = f"{new_first} {new_last}"

    # Update profile JSON
    profile = student.profile or {}
    if "class_id" in update_data:
        profile["class_id"] = str(update_data["class_id"]) if update_data["class_id"] else None
    if "parent_email" in update_data:
        profile["parent_email"] = update_data["parent_email"]
    if "parent_phone" in update_data:
        profile["parent_phone"] = update_data["parent_phone"]
        student.phone = update_data["parent_phone"]
    if created_parent_ids:
        profile["parents_id"] = created_parent_ids
    
    student.profile = profile
    
    db.commit()
    db.refresh(student)
    
    logger.info(f"Student updated successfully: {student.display_name}")
    return success_response(user_to_student_dict(student))
