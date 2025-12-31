from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime
import os
import shutil
from app.core.database import get_auth_db  # Changed to use auth database
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.models.school import School
from app.schemas.school import SchoolCreate, SchoolResponse, SchoolUpdate, SchoolOnboardingRequest, SchoolOnboardingResponse

# Initialize logger
logger = get_logger(__name__)

router = APIRouter()

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_school(
    school_data: SchoolCreate,
    db: Session = Depends(get_auth_db)  # Changed to use auth database
):
    logger.info(f"Creating school: {school_data.name}")
    school = School(**school_data.dict())
    db.add(school)
    db.commit()
    db.refresh(school)
    logger.info(f"School created", extra={"extra_data": {"school_id": str(school.school_id)}})
    return success_response(school)

@router.get("")
async def list_schools(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_auth_db)  # Changed to use auth database
):
    logger.debug("Listing schools")
    schools = db.query(School).offset(skip).limit(limit).all()
    logger.debug(f"Found {len(schools)} schools")
    
    # Add needs_data_onboarding flag from settings
    schools_data = []
    for school in schools:
        school_dict = {
            "school_id": school.school_id,
            "name": school.name,
            "address": school.address,
            "city": school.city,
            "state": school.state,
            "country": school.country,
            "phone": school.phone,
            "email": school.email,
            "website": school.website,
            "timezone": school.timezone,
            "academic_year": school.academic_year,
            "needs_data_onboarding": school.settings.get("needs_data_onboarding", False) if school.settings else False,
            "logo_url": school.logo_url
        }
        schools_data.append(school_dict)
    
    return success_response(schools_data)

@router.get("/{school_id}")
async def get_school(
    school_id: UUID,
    db: Session = Depends(get_auth_db)  # Uses auth database for schools
):
    logger.debug(f"Fetching school: {school_id}")
    school = db.query(School).filter(School.school_id == school_id).first()
    if not school:
        logger.warning(f"School not found: {school_id}")
        raise HTTPException(status_code=404, detail="School not found")
    
    # Include needs_data_onboarding flag from settings
    school_dict = {
        "school_id": school.school_id,
        "name": school.name,
        "address": school.address,
        "city": school.city,
        "state": school.state,
        "country": school.country,
        "phone": school.phone,
        "email": school.email,
        "website": school.website,
        "timezone": school.timezone,
        "academic_year": school.academic_year,
        "settings": school.settings,
        "needs_data_onboarding": school.settings.get("needs_data_onboarding", False) if school.settings else False,
        "logo_url": school.logo_url
    }
    
    return success_response(school_dict)

@router.patch("/{school_id}")
async def update_school(
    school_id: UUID,
    school_update: SchoolUpdate,
    db: Session = Depends(get_auth_db)  # Uses auth database for schools
):
    school = db.query(School).filter(School.school_id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    for field, value in school_update.dict(exclude_unset=True).items():
        setattr(school, field, value)

    db.commit()
    db.refresh(school)
    return success_response(school)

@router.delete("/{school_id}")
async def delete_school(
    school_id: UUID,
    db: Session = Depends(get_auth_db)  # Uses auth database for schools
):
    logger.info(f"Deleting school: {school_id}")
    school = db.query(School).filter(School.school_id == school_id).first()
    if not school:
        logger.warning(f"School deletion failed - not found: {school_id}")
        raise HTTPException(status_code=404, detail="School not found")

    # Check for dependent records before deletion
    dependent_records = []

    if school.users:
        dependent_records.append(f"{len(school.users)} user(s)")
    if school.students:
        dependent_records.append(f"{len(school.students)} student(s)")
    if school.classes:
        dependent_records.append(f"{len(school.classes)} class(es)")
    if school.resources:
        dependent_records.append(f"{len(school.resources)} resource(s)")

    if dependent_records:
        logger.warning(f"School deletion blocked - has dependencies", extra={"extra_data": {"school_id": str(school_id), "dependencies": dependent_records}})
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact Technical Support to request the deletion process."
        )

    db.delete(school)
    db.commit()
    logger.info(f"School deleted", extra={"extra_data": {"school_id": str(school_id)}})
    return success_response({"message": "School deleted successfully", "school_id": str(school_id)})

@router.post("/onboarding", status_code=status.HTTP_201_CREATED)
async def submit_school_onboarding(
    onboarding_data: SchoolOnboardingRequest,
    db: Session = Depends(get_auth_db)  # Uses auth database for schools
):
    """
    Submit a school onboarding application.
    This endpoint receives school registration requests and stores them for review.
    """
    
    # Validate terms acceptance
    if not onboarding_data.termsAccepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Terms and conditions must be accepted"
        )
    
    # Check if school with same email already exists
    existing_school = db.query(School).filter(School.email == onboarding_data.schoolEmail).first()
    if existing_school:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A school with this email address already exists"
        )
    
    # Generate application ID
    application_id = f"APP-{datetime.utcnow().strftime('%Y%m%d')}-{db.query(School).count() + 1:04d}"
    
    # Create school record with pending status
    school_data = SchoolCreate(
        name=onboarding_data.schoolName,
        address=onboarding_data.address,
        city=onboarding_data.city,
        state=onboarding_data.state,
        country="India",
        phone=onboarding_data.schoolPhone,
        email=onboarding_data.schoolEmail,
        website=onboarding_data.websiteUrl,
        timezone="America/New_York",  # Default, can be updated later
        academic_year=f"{datetime.utcnow().year}-{datetime.utcnow().year + 1}",
        settings={
            "onboarding_status": "pending_review",
            "application_id": application_id,
            "school_type": onboarding_data.schoolType,
            "established_year": onboarding_data.establishedYear,
            "registration_number": onboarding_data.registrationNumber,
            "contact_person": {
                "name": onboarding_data.contactPersonName,
                "email": onboarding_data.contactPersonEmail,
                "phone": onboarding_data.contactPersonPhone,
                "designation": onboarding_data.contactPersonDesignation
            },
            "zip_code": onboarding_data.zipCode,
            "submitted_at": datetime.utcnow().isoformat(),
            "needs_data_onboarding": True  # New schools need data onboarding
        }
    )
    
    school = School(**school_data.dict())
    db.add(school)
    db.commit()
    db.refresh(school)
    
    # Create principal user account from contact person information
    from app.models.user import User
    from app.core.security import get_password_hash
    
    try:
        principal_user = User(
            school_id=school.school_id,
            display_name=onboarding_data.contactPersonName,
            email=onboarding_data.contactPersonEmail,
            role='PRINCIPAL',
            phone=onboarding_data.contactPersonPhone,
            hashed_password=get_password_hash('Welcome123!'),  # Default password
            profile={
                'designation': onboarding_data.contactPersonDesignation,
                'is_primary_contact': True
            }
        )
        db.add(principal_user)
        db.commit()
        db.refresh(principal_user)
    except Exception as e:
        # Log error but don't fail the school creation
        print(f"Warning: Failed to create principal user: {str(e)}")
    
    # Prepare response
    response = SchoolOnboardingResponse(
        message="School onboarding application submitted successfully",
        application_id=application_id,
        school_email=onboarding_data.schoolEmail,
        status="pending_review",
        submitted_at=datetime.utcnow()
    )
    
    return success_response(response.dict())


@router.patch("/{school_id}/complete-onboarding")
async def complete_data_onboarding(
    school_id: UUID,
    db: Session = Depends(get_auth_db)  # Uses auth database for schools
):
    """
    Mark data onboarding as complete for a school.
    """
    school = db.query(School).filter(School.school_id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Update settings to mark onboarding as complete
    if school.settings is None:
        school.settings = {}
    
    # Create a new dict to trigger SQLAlchemy's change detection for JSON fields
    new_settings = dict(school.settings)
    new_settings["needs_data_onboarding"] = False
    new_settings["data_onboarding_completed_at"] = datetime.utcnow().isoformat()
    school.settings = new_settings
    
    db.commit()
    db.refresh(school)
    
    return success_response({
        "message": "Data onboarding marked as complete",
        "school_id": str(school_id)
    })

@router.post("/{school_id}/upload-staff", status_code=status.HTTP_201_CREATED)
async def upload_staff_data(
    school_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_auth_db)  # Uses auth database for schools
):
    """
    Upload staff (teachers and counsellors) data from Excel file.
    Expected columns: first_name, last_name, email, role (teacher/counsellor), phone, subject (for teachers)
    """
    import pandas as pd
    from io import BytesIO
    from app.models.user import User
    from app.core.security import get_password_hash
    
    # Verify school exists
    school = db.query(School).filter(School.school_id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)"
        )
    
    try:
        # Read Excel file
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
        
        # Validate required columns
        required_columns = ['first_name', 'last_name', 'email', 'role']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        created_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Check if user already exists
                existing_user = db.query(User).filter(User.email == row['email']).first()
                if existing_user:
                    errors.append(f"Row {index + 2}: User with email {row['email']} already exists")
                    continue
                
                # Combine first and last name into display_name
                display_name = f"{row['first_name']} {row['last_name']}"
                
                # Validate role
                role_upper = row['role'].upper()
                if role_upper not in ['TEACHER', 'COUNSELLOR', 'PRINCIPAL']:
                    errors.append(f"Row {index + 2}: Invalid role '{row['role']}'. Must be 'teacher', 'counsellor', or 'principal'")
                    continue
                
                # Create user profile with subject info
                profile = {}
                if pd.notna(row.get('subject')):
                    profile['subject'] = row['subject']
                
                # Create user
                user = User(
                    school_id=school_id,
                    display_name=display_name,
                    email=row['email'],
                    role=role_upper,
                    phone=row.get('phone') if pd.notna(row.get('phone')) else None,
                    hashed_password=get_password_hash('Welcome123!'),  # Default password
                    profile=profile if profile else None
                )
                
                db.add(user)
                created_count += 1
                
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
        
        db.commit()
        
        return success_response({
            "count": created_count,
            "message": f"Successfully uploaded {created_count} staff members",
            "errors": errors if errors else None
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}"
        )

@router.post("/{school_id}/upload-students", status_code=status.HTTP_201_CREATED)
async def upload_students_data(
    school_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_auth_db)  # Uses auth database for schools
):
    """
    Upload students and parents data from Excel file.
    Expected columns: first_name, last_name, date_of_birth, grade, gender, 
                     parent_name, parent_email, parent_phone, parent_relationship
    
    This endpoint will:
    1. Create parent User records if they don't exist
    2. Create student records
    3. Link students to parents via parents_id field
    """
    import pandas as pd
    from io import BytesIO
    from app.models.student import Student
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash
    from datetime import datetime
    
    # Verify school exists
    school = db.query(School).filter(School.school_id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)"
        )
    
    try:
        # Read Excel file
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
        
        # Validate required columns
        required_columns = ['first_name', 'last_name', 'date_of_birth', 'grade', 'gender']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        created_students = 0
        created_parents = 0
        errors = []
        
        # Cache for parent lookups
        parent_cache = {}
        
        for index, row in df.iterrows():
            try:
                # Parse date of birth
                dob = pd.to_datetime(row['date_of_birth']).date()
                
                # Validate gender
                gender_value = row['gender'].upper().replace(' ', '_')
                if gender_value not in ['MALE', 'FEMALE', 'OTHER', 'PREFER_NOT_TO_SAY']:
                    gender_value = 'OTHER'
                
                # Handle parent creation/lookup
                parent_ids = []
                parent_email = row.get('parent_email')
                parent_name = row.get('parent_name')
                parent_phone = row.get('parent_phone')
                
                if pd.notna(parent_email) and parent_email:
                    parent_email = str(parent_email).strip()
                    
                    # Check cache first
                    if parent_email in parent_cache:
                        parent_ids.append(str(parent_cache[parent_email]))
                    else:
                        # Check if parent user already exists
                        parent_user = db.query(User).filter(
                            User.email == parent_email,
                            User.school_id == school_id
                        ).first()
                        
                        if not parent_user:
                            # Create new parent user
                            display_name = parent_name if pd.notna(parent_name) else f"Parent of {row['first_name']} {row['last_name']}"
                            
                            parent_user = User(
                                school_id=school_id,
                                role=UserRole.PARENT,
                                email=parent_email,
                                hashed_password=get_password_hash("WellNest2024!"),  # Default password
                                display_name=display_name,
                                phone=parent_phone if pd.notna(parent_phone) else None,
                                profile={
                                    "preferred_contact_method": "email",
                                    "languages": ["English"],
                                    "relationship": row.get('parent_relationship', 'Parent') if pd.notna(row.get('parent_relationship')) else 'Parent'
                                }
                            )
                            db.add(parent_user)
                            db.flush()  # Get the user_id
                            created_parents += 1
                        
                        parent_cache[parent_email] = parent_user.user_id
                        parent_ids.append(str(parent_user.user_id))
                
                # Store additional parent info
                additional_info = {}
                if pd.notna(parent_name):
                    additional_info['parent_name'] = parent_name
                if pd.notna(row.get('parent_relationship')):
                    additional_info['parent_relationship'] = row.get('parent_relationship', 'Parent')
                
                # Create student with parent linkage
                student = Student(
                    school_id=school_id,
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    dob=dob,
                    grade=str(row['grade']),
                    gender=gender_value,
                    parent_email=parent_email if pd.notna(parent_email) else None,
                    parent_phone=parent_phone if pd.notna(parent_phone) else None,
                    parents_id=parent_ids if parent_ids else None,  # Link to parent users
                    additional_info=additional_info if additional_info else None
                )
                
                db.add(student)
                created_students += 1
                
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
        
        db.commit()
        
        return success_response({
            "count": created_students,
            "message": f"Successfully uploaded {created_students} students and {created_parents} parents",
            "students_created": created_students,
            "parents_created": created_parents,
            "errors": errors if errors else None
        })
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}"
        )

@router.post("/{school_id}/upload-classes", status_code=status.HTTP_201_CREATED)
async def upload_classes_data(
    school_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_auth_db)  # Uses auth database for schools
):
    """
    Upload classes data from Excel file.
    Expected columns: class_name, grade, section, teacher_email, subject, room_number
    """
    import pandas as pd
    from io import BytesIO
    from app.models.class_model import Class
    from app.models.user import User
    
    # Verify school exists
    school = db.query(School).filter(School.school_id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)"
        )
    
    try:
        # Read Excel file
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
        
        # Validate required columns
        required_columns = ['class_name', 'grade', 'section', 'teacher_email']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        created_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Find teacher
                teacher = db.query(User).filter(
                    User.email == row['teacher_email'],
                    User.school_id == school_id,
                    User.role == 'TEACHER'
                ).first()
                
                if not teacher:
                    errors.append(f"Row {index + 2}: Teacher with email {row['teacher_email']} not found")
                    continue
                
                # Store subject and room_number in additional_info
                additional_info = {}
                if pd.notna(row.get('subject')):
                    additional_info['subject'] = row['subject']
                if pd.notna(row.get('room_number')):
                    additional_info['room_number'] = row['room_number']
                
                # Create class
                class_obj = Class(
                    school_id=school_id,
                    teacher_id=teacher.user_id,
                    name=row['class_name'],
                    grade=str(row['grade']),
                    section=row['section'],
                    academic_year=school.academic_year,
                    additional_info=additional_info if additional_info else None
                )
                
                db.add(class_obj)
                created_count += 1
                
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
        
        db.commit()
        
        return success_response({
            "count": created_count,
            "message": f"Successfully uploaded {created_count} classes",
            "errors": errors if errors else None
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}"
        )

@router.post("/{school_id}/logo")
async def upload_school_logo(
    school_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_auth_db)  # Uses auth database for schools
):
    """
    Upload a school logo.
    """
    school = db.query(School).filter(School.school_id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload an image."
        )

    # Create directory if it doesn't exist
    upload_dir = "uploads/logos"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate filename
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{school_id}{file_extension}"
    file_path = os.path.join(upload_dir, filename)

    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    # Update school logo_url
    # Store relative path, frontend will need to handle base URL
    logo_url = f"/uploads/logos/{filename}"
    
    school.logo_url = logo_url
    db.commit()
    db.refresh(school)

    return success_response({
        "message": "Logo uploaded successfully",
        "logo_url": logo_url,
        "school_id": str(school_id)
    })
