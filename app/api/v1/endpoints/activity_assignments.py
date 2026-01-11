from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.api.dependencies import get_db, get_current_user
from app.core.logging_config import get_logger
from app.models.user import User
from app.models.activity_assignment import ActivityAssignment, AssignmentStatus
from app.models.activity_submission import ActivitySubmission, SubmissionStatus, FileType
from app.models.student import Student
from app.models.class_model import Class
from pydantic import BaseModel

# Initialize logger
logger = get_logger(__name__)

router = APIRouter()

# Schemas (Internal for now, can be moved to app/schemas later)
class AssignmentCreate(BaseModel):
    activity_id: UUID
    class_id: UUID
    due_date: Optional[datetime] = None

class ActivitySimpleSchema(BaseModel):
    activity_id: UUID
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    type: Optional[str] = None
    duration: Optional[int] = None
    target_grades: Optional[List[str]] = None
    location: Optional[str] = None
    risk_level: Optional[str] = None
    skill_level: Optional[str] = None
    theme: Optional[List[str]] = None
    
    class Config:
        from_attributes = True

class AssignmentResponse(BaseModel):
    assignment_id: UUID
    activity_id: UUID
    class_id: UUID
    due_date: Optional[datetime]
    status: str
    created_at: datetime
    activity: Optional[ActivitySimpleSchema] = None
    submission_count: int = 0
    total_students: int = 0
    
    class Config:
        from_attributes = True

class SubmissionUpdate(BaseModel):
    status: SubmissionStatus
    feedback: Optional[str] = None

class ClassStats(BaseModel):
    class_id: UUID
    name: str
    student_count: int
    active_activity_count: int
    
    class Config:
        from_attributes = True

class DashboardStatsResponse(BaseModel):
    active_assignments: int
    pending_reviews: int
    total_students: int
    classes: List[ClassStats]

# --- Assignments ---

@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard statistics for the current teacher"""
    # 1. Get all classes for this teacher
    classes = db.query(Class).filter(Class.teacher_id == current_user.user_id).all()
    
    class_stats_list = []
    total_students = 0
    
    for cls in classes:
        # Count students
        s_count = db.query(Student).filter(Student.class_id == cls.class_id).count()
        total_students += s_count
        
        # Count active assignments
        a_count = db.query(ActivityAssignment).filter(
            ActivityAssignment.class_id == cls.class_id,
            ActivityAssignment.status == AssignmentStatus.ACTIVE
        ).count()
        
        class_stats_list.append(ClassStats(
            class_id=cls.class_id,
            name=cls.name,
            student_count=s_count,
            active_activity_count=a_count
        ))
        
    # 2. Global Active Assignments (assigned by this teacher)
    active_assignments = db.query(ActivityAssignment).filter(
        ActivityAssignment.assigned_by == current_user.user_id,
        ActivityAssignment.status == AssignmentStatus.ACTIVE
    ).count()
    
    # 3. Pending Reviews (Submissions with status SUBMITTED for assignments by this teacher)
    pending_reviews = db.query(ActivitySubmission).join(ActivityAssignment).filter(
        ActivityAssignment.assigned_by == current_user.user_id,
        ActivitySubmission.status == SubmissionStatus.SUBMITTED
    ).count()
    
    return DashboardStatsResponse(
        active_assignments=active_assignments,
        pending_reviews=pending_reviews,
        total_students=total_students,
        classes=class_stats_list
    )

@router.post("/assignments", response_model=AssignmentResponse)
def create_assignment(
    assignment: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign an activity to a class"""
    # Verify class exists
    class_obj = db.query(Class).filter(Class.class_id == assignment.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")

    new_assignment = ActivityAssignment(
        activity_id=assignment.activity_id,
        class_id=assignment.class_id,
        assigned_by=current_user.user_id,
        due_date=assignment.due_date
    )
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    
    # Create pending submissions for all students in the class
    students = db.query(Student).filter(Student.class_id == assignment.class_id).all()
    for student in students:
        submission = ActivitySubmission(
            assignment_id=new_assignment.assignment_id,
            student_id=student.student_id,
            status=SubmissionStatus.PENDING
        )
        db.add(submission)
    
    db.commit()
    return new_assignment

@router.get("/assignments/class/{class_id}", response_model=List[AssignmentResponse])
def get_class_assignments(
    class_id: UUID,
    db: Session = Depends(get_db)
):
    """Get all assignments for a class"""
    assignments = db.query(ActivityAssignment).filter(
        ActivityAssignment.class_id == class_id,
        ActivityAssignment.status == AssignmentStatus.ACTIVE
    ).all()

    result = []
    for assignment in assignments:
        submissions = db.query(ActivitySubmission).filter(
            ActivitySubmission.assignment_id == assignment.assignment_id
        ).all()
        
        total_students = len(submissions)
        # Count submissions that are NOT pending (i.e. submitted, verified, or rejected)
        submission_count = len([s for s in submissions if s.status != SubmissionStatus.PENDING])
        
        assignment_dict = {
            "assignment_id": assignment.assignment_id,
            "activity_id": assignment.activity_id,
            "class_id": assignment.class_id,
            "due_date": assignment.due_date,
            "status": assignment.status,
            "created_at": assignment.created_at,
            "activity": None,  # Activity details fetched from external service by frontend
            "submission_count": submission_count,
            "total_students": total_students
        }
        result.append(assignment_dict)
        
    return result

# --- Submissions ---

@router.get("/submissions/assignment/{assignment_id}")
def get_assignment_submissions(
    assignment_id: UUID,
    db: Session = Depends(get_db)
):
    """Get all submissions for an assignment (Teacher Dashboard)"""
    submissions = db.query(ActivitySubmission).filter(
        ActivitySubmission.assignment_id == assignment_id
    ).all()
    
    # Enrich with student details manually for now (or use a Schema with relationships)
    result = []
    for sub in submissions:
        student = db.query(Student).get(sub.student_id)
        result.append({
            "submission_id": sub.submission_id,
            "student_id": sub.student_id,
            "student_name": f"{student.first_name} {student.last_name}",
            "file_url": sub.file_url,
            "status": sub.status,
            "submitted_at": sub.submitted_at,
            "feedback": sub.feedback
        })
    return result

@router.get("/submissions/student/{student_id}")
def get_student_submissions(
    student_id: UUID,
    db: Session = Depends(get_db)
):
    """Get all submissions for a student"""
    return db.query(ActivitySubmission).filter(
        ActivitySubmission.student_id == student_id
    ).all()

@router.post("/submissions")
async def submit_activity(
    assignment_id: UUID = Form(...),
    student_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Submit an activity response (Student)"""
    # Find the submission record
    submission = db.query(ActivitySubmission).filter(
        ActivitySubmission.assignment_id == assignment_id,
        ActivitySubmission.student_id == student_id
    ).first()
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission record not found")
    
    # TODO: Upload file to S3/Cloud Storage. For now, we'll simulate a URL.
    # In a real app, save `file` to disk or cloud and get the URL.
    fake_url = f"https://fake-storage.com/{file.filename}" 
    
    submission.file_url = fake_url
    submission.file_type = FileType.IMAGE if "image" in file.content_type else FileType.VIDEO
    submission.status = SubmissionStatus.SUBMITTED
    submission.submitted_at = datetime.utcnow()
    
    db.commit()
    db.refresh(submission)
    return submission

@router.put("/submissions/{submission_id}")
def review_submission(
    submission_id: UUID,
    update: SubmissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Review a submission (Teacher)"""
    submission = db.query(ActivitySubmission).get(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    submission.status = update.status
    submission.feedback = update.feedback
    
    db.commit()
    db.refresh(submission)
    return submission

# --- Comments ---

class CommentCreate(BaseModel):
    message: str

class CommentResponse(BaseModel):
    comment_id: UUID
    submission_id: UUID
    user_id: Optional[UUID]
    student_id: Optional[UUID]
    message: str
    created_at: datetime
    sender_name: Optional[str] = None
    
    class Config:
        from_attributes = True

@router.get("/submissions/{submission_id}/comments", response_model=List[CommentResponse])
def get_submission_comments(
    submission_id: UUID,
    db: Session = Depends(get_db)
):
    """Get all comments for a submission"""
    from app.models.activity_submission import SubmissionComment
    
    comments = db.query(SubmissionComment).filter(
        SubmissionComment.submission_id == submission_id
    ).order_by(SubmissionComment.created_at.asc()).all()
    
    # Enrich with sender names
    import re
    def clean_name(name: str) -> str:
        if not name:
            return name
        return re.sub(r'^(Ms\.|Mr\.|Mrs\.|Dr\.|Prof\.)\s*', '', name, flags=re.IGNORECASE)

    result = []
    for comment in comments:
        sender_name = "Unknown"
        if comment.user_id:
            user = db.query(User).get(comment.user_id)
            sender_name = clean_name(user.display_name) if user else "Teacher"
        elif comment.student_id:
            student = db.query(Student).get(comment.student_id)
            sender_name = f"{student.first_name} {student.last_name}" if student else "Student"
            
        result.append({
            "comment_id": comment.comment_id,
            "submission_id": comment.submission_id,
            "user_id": comment.user_id,
            "student_id": comment.student_id,
            "message": comment.message,
            "created_at": comment.created_at,
            "sender_name": sender_name
        })
    return result

@router.post("/submissions/{submission_id}/comments", response_model=CommentResponse)
def add_submission_comment(
    submission_id: UUID,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user) # This might fail for students if they use a different auth dependency
):
    """Add a comment to a submission (Teacher or Student)"""
    from app.models.activity_submission import SubmissionComment, ActivitySubmission
    import re
    
    submission = db.query(ActivitySubmission).get(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Determine sender
    user_id = None
    student_id = None
    
    if current_user:
        user_id = current_user.user_id
    else:
        # TODO: Handle student auth
        pass

    new_comment = SubmissionComment(
        submission_id=submission_id,
        user_id=user_id,
        student_id=student_id,
        message=comment.message
    )
    
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    
    # Return with sender name
    def clean_name(name: str) -> str:
        if not name:
            return name
        return re.sub(r'^(Ms\.|Mr\.|Mrs\.|Dr\.|Prof\.)\s*', '', name, flags=re.IGNORECASE)

    sender_name = clean_name(current_user.display_name) if current_user else "Unknown"
    
    return {
        "comment_id": new_comment.comment_id,
        "submission_id": new_comment.submission_id,
        "user_id": new_comment.user_id,
        "student_id": new_comment.student_id,
        "message": new_comment.message,
        "created_at": new_comment.created_at,
        "sender_name": sender_name
    }
