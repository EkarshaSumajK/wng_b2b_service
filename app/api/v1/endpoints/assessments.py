from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
import statistics
from app.core.database import get_db
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.core.student_helpers import get_student_by_id, user_to_student_dict
from app.models.assessment import Assessment, AssessmentTemplate, StudentResponse
from app.models.class_model import Class
from app.models.user import User, UserRole
from app.schemas.assessment import (
    AssessmentCreate, AssessmentResponse, AssessmentSubmit,
    AssessmentTemplateCreate, AssessmentTemplateUpdate, AssessmentTemplateResponse,
    AssessmentListResponse, StudentAssessmentResult
)

# Initialize logger
logger = get_logger(__name__)

router = APIRouter()

# ============== HELPER FUNCTIONS ==============

def calculate_score(answer, question_info: Dict[str, Any]) -> float:
    """Calculate score for a single answer based on question type"""
    question_type = question_info.get('question_type')
    
    if question_type in ['rating_scale', 'likert_scale']:
        return float(answer) if answer is not None else 0.0
    elif question_type == 'multiple_choice':
        options = question_info.get('answer_options', [])
        for opt in options:
            if opt.get('option_id') == answer:
                return float(opt.get('value', 0))
        return 0.0
    elif question_type == 'yes_no':
        return 1.0 if answer else 0.0
    return 0.0

def get_or_404(db: Session, model, filter_expr, error_msg: str):
    """Generic helper to get a record or raise 404"""
    result = db.query(model).filter(filter_expr).first()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    return result

def calculate_statistics(scores: List[float]) -> Dict[str, Any]:
    """Calculate comprehensive statistics for a list of scores"""
    if not scores:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std_dev": None,
            "count": 0
        }
    
    return {
        "min": round(min(scores), 2),
        "max": round(max(scores), 2),
        "mean": round(statistics.mean(scores), 2),
        "median": round(statistics.median(scores), 2),
        "std_dev": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0.0,
        "count": len(scores)
    }

def build_assessment_list_response(assessment: Assessment) -> Dict[str, Any]:
    """Build simple assessment info for listing"""
    return {
        "assessment_id": assessment.assessment_id,
        "template_id": assessment.template_id,
        "template_name": assessment.template.name,
        "school_id": assessment.school_id,
        "class_id": assessment.class_id,
        "class_name": assessment.class_obj.name if assessment.class_obj else None,
        "title": assessment.title,
        "category": assessment.category or (assessment.template.category if assessment.template else None),
        "created_by": assessment.created_by,
        "created_at": assessment.created_at,
        "notes": assessment.notes
    }

# ============== TEMPLATE ENDPOINTS ==============

@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: AssessmentTemplateCreate,
    db: Session = Depends(get_db)
):
    """Create a new assessment template"""
    get_or_404(db, User, User.user_id == template_data.created_by, "Creator not found")
    
    template = AssessmentTemplate(
        name=template_data.name,
        description=template_data.description,
        category=template_data.category,
        questions=[q.dict() for q in template_data.questions],
        scoring_rules=template_data.scoring_rules,
        created_by=template_data.created_by
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return success_response(template)

@router.get("/templates")
async def list_templates(
    skip: int = 0,
    limit: int = 100,
    category: str = None,
    is_active: bool = None,
    db: Session = Depends(get_db)
):
    """List all assessment templates"""
    query = db.query(AssessmentTemplate)
    
    if category:
        query = query.filter(AssessmentTemplate.category == category)
    if is_active is not None:
        query = query.filter(AssessmentTemplate.is_active == is_active)
    
    templates = query.offset(skip).limit(limit).all()
    return success_response(templates)

@router.get("/templates/{template_id}")
async def get_template(
    template_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a specific assessment template"""
    template = get_or_404(
        db, AssessmentTemplate, 
        AssessmentTemplate.template_id == template_id,
        "Template not found"
    )
    return success_response(template)

@router.patch("/templates/{template_id}")
async def update_template(
    template_id: UUID,
    template_update: AssessmentTemplateUpdate,
    db: Session = Depends(get_db)
):
    """Update an assessment template"""
    template = get_or_404(
        db, AssessmentTemplate,
        AssessmentTemplate.template_id == template_id,
        "Template not found"
    )
    
    update_data = template_update.dict(exclude_unset=True)
    if "questions" in update_data and update_data["questions"]:
        update_data["questions"] = [q.dict() for q in update_data["questions"]]
    
    for field, value in update_data.items():
        setattr(template, field, value)
    
    template.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(template)
    
    return success_response(template)

@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db)
):
    """Soft delete a template by marking it inactive"""
    template = get_or_404(
        db, AssessmentTemplate,
        AssessmentTemplate.template_id == template_id,
        "Template not found"
    )
    
    template.is_active = False
    db.commit()
    
    return success_response({"message": "Template deactivated successfully"})

# ============== ASSESSMENT ENDPOINTS ==============

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_assessment(
    assessment_data: AssessmentCreate,
    db: Session = Depends(get_db)
):
    """Create a new assessment (can be assigned to a class or school-wide)
    
    Can be created in two ways:
    1. Using an existing template (provide template_id)
    2. With custom questions (provide questions array)
    """
    # Validate creator exists
    get_or_404(db, User, User.user_id == assessment_data.created_by, "Creator not found")
    
    if assessment_data.class_id:
        get_or_404(db, Class, Class.class_id == assessment_data.class_id, "Class not found")

    template_id = assessment_data.template_id
    
    # If no template_id provided, create a template from questions
    if not template_id and assessment_data.questions:
        # Create a template on-the-fly
        template = AssessmentTemplate(
            name=assessment_data.title or "Custom Assessment",
            description=assessment_data.description,
            category=assessment_data.category,
            questions=[q.dict() for q in assessment_data.questions],
            scoring_rules={},
            created_by=assessment_data.created_by,
            is_active=True
        )
        db.add(template)
        db.flush()  # Get the template_id without committing
        template_id = template.template_id
    elif not template_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either template_id or questions must be provided"
        )
    else:
        # Validate template exists
        get_or_404(db, AssessmentTemplate, AssessmentTemplate.template_id == template_id, "Template not found")

    assessment = Assessment(
        template_id=template_id,
        school_id=assessment_data.school_id,
        class_id=assessment_data.class_id,
        title=assessment_data.title,
        category=assessment_data.category,
        created_by=assessment_data.created_by,
        notes=assessment_data.notes
    )

    db.add(assessment)
    db.commit()
    
    # Fetch with relationships for response
    assessment = (
        db.query(Assessment)
        .options(joinedload(Assessment.template), joinedload(Assessment.class_obj))
        .filter(Assessment.assessment_id == assessment.assessment_id)
        .first()
    )

    return success_response(build_assessment_list_response(assessment))

@router.patch("/{assessment_id}/exclude-student/{student_id}")
async def exclude_student_from_assessment(
    assessment_id: UUID,
    student_id: UUID,
    db: Session = Depends(get_db)
):
    """Exclude a specific student from a class assessment"""
    assessment = get_or_404(db, Assessment, Assessment.assessment_id == assessment_id, "Assessment not found")
    
    # Initialize excluded_students if None
    if assessment.excluded_students is None:
        assessment.excluded_students = []
    
    # Add student to exclusion list if not already there
    if student_id not in assessment.excluded_students:
        assessment.excluded_students = assessment.excluded_students + [student_id]
        db.commit()
        db.refresh(assessment)
    
    return success_response({"message": "Student excluded from assessment", "excluded_students": assessment.excluded_students})

@router.patch("/{assessment_id}/include-student/{student_id}")
async def include_student_in_assessment(
    assessment_id: UUID,
    student_id: UUID,
    db: Session = Depends(get_db)
):
    """Re-include a student in a class assessment (remove from exclusion list)"""
    assessment = get_or_404(db, Assessment, Assessment.assessment_id == assessment_id, "Assessment not found")
    
    # Remove student from exclusion list if present
    if assessment.excluded_students and student_id in assessment.excluded_students:
        assessment.excluded_students = [sid for sid in assessment.excluded_students if sid != student_id]
        db.commit()
        db.refresh(assessment)
    
    return success_response({"message": "Student included in assessment", "excluded_students": assessment.excluded_students})

@router.post("/submit")
async def submit_assessment(
    submission: AssessmentSubmit,
    db: Session = Depends(get_db)
):
    """Submit responses to an assessment for a specific student"""
    assessment = (
        db.query(Assessment)
        .options(joinedload(Assessment.template))
        .filter(Assessment.assessment_id == submission.assessment_id)
        .first()
    )
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Validate student exists (now in b2b_users with role=STUDENT)
    student = get_student_by_id(db, submission.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check if student already completed this assessment
    existing = db.query(StudentResponse).filter(
        StudentResponse.assessment_id == submission.assessment_id,
        StudentResponse.student_id == submission.student_id
    ).first()
    
    if existing and existing.completed_at:
        raise HTTPException(status_code=400, detail="Student has already completed this assessment")

    questions_map = {q['question_id']: q for q in assessment.template.questions}
    
    # Delete existing responses if any (allows re-submission if not marked complete)
    db.query(StudentResponse).filter(
        StudentResponse.assessment_id == submission.assessment_id,
        StudentResponse.student_id == submission.student_id
    ).delete()
    
    # Create and score responses
    total_score = 0.0
    for response_data in submission.responses:
        if response_data.question_id not in questions_map:
            raise HTTPException(status_code=400, detail=f"Invalid question: {response_data.question_id}")
        
        question_info = questions_map[response_data.question_id]
        score = calculate_score(response_data.answer, question_info)
        total_score += score
        
        db.add(StudentResponse(
            assessment_id=submission.assessment_id,
            student_id=submission.student_id,
            question_id=response_data.question_id,
            question_text=question_info['question_text'],
            answer=response_data.answer,
            score=score,
            completed_at=datetime.utcnow()  # Mark as completed
        ))
    
    db.commit()
    
    # Return student's responses
    responses = db.query(StudentResponse).filter(
        StudentResponse.assessment_id == submission.assessment_id,
        StudentResponse.student_id == submission.student_id
    ).all()

    return success_response({
        "assessment_id": submission.assessment_id,
        "student_id": submission.student_id,
        "student_name": student.display_name,
        "total_score": total_score,
        "completed_at": datetime.utcnow(),
        "responses": [{
            "response_id": r.response_id,
            "question_id": r.question_id,
            "question_text": r.question_text,
            "answer": r.answer,
            "score": r.score,
            "created_at": r.created_at
        } for r in responses]
    })

@router.get("/{assessment_id}")
async def get_assessment(
    assessment_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a specific assessment details with all student results"""
    assessment = (
        db.query(Assessment)
        .options(
            joinedload(Assessment.template),
            joinedload(Assessment.class_obj),
            joinedload(Assessment.responses)
        )
        .filter(Assessment.assessment_id == assessment_id)
        .first()
    )

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Group responses by student
    student_data = {}
    for response in assessment.responses:
        if response.student_id not in student_data:
            student = get_student_by_id(db, response.student_id)
            student_name = student.display_name if student else "Unknown"
            student_data[response.student_id] = {
                "student_id": response.student_id,
                "student_name": student_name,
                "responses": [],
                "total_score": 0.0,
                "completed_at": response.completed_at
            }
        
        student_data[response.student_id]["responses"].append({
            "response_id": response.response_id,
            "question_id": response.question_id,
            "question_text": response.question_text,
            "answer": response.answer,
            "score": response.score,
            "created_at": response.created_at
        })
        student_data[response.student_id]["total_score"] += response.score or 0.0

    return success_response({
        "assessment_id": assessment.assessment_id,
        "template": {
            "template_id": assessment.template.template_id,
            "name": assessment.template.name,
            "category": assessment.template.category,
            "questions": assessment.template.questions
        },
        "template_name": assessment.template.name,
        "school_id": assessment.school_id,
        "class_id": assessment.class_id,
        "class_name": assessment.class_obj.name if assessment.class_obj else None,
        "title": assessment.title,
        "category": assessment.category or assessment.template.category,
        "created_by": assessment.created_by,
        "created_at": assessment.created_at,
        "notes": assessment.notes,
        "student_results": list(student_data.values())
    })

@router.get("")
async def list_assessments(
    school_id: Optional[UUID] = None,
    class_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List assessments with optional filters"""
    query = (
        db.query(Assessment)
        .options(joinedload(Assessment.template), joinedload(Assessment.class_obj))
    )
    
    if school_id:
        query = query.filter(Assessment.school_id == school_id)
    
    if class_id:
        query = query.filter(Assessment.class_id == class_id)

    assessments = query.offset(skip).limit(limit).all()
    return success_response([build_assessment_list_response(a) for a in assessments])


# ============== RESULT ENDPOINTS ==============

@router.get("/results/student/{student_id}")
async def get_student_assessments(
    student_id: UUID,
    db: Session = Depends(get_db)
):
    """Get all completed assessments for one student with overall statistics and detailed responses"""
    student = get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get all responses for this student
    responses = (
        db.query(StudentResponse)
        .options(
            joinedload(StudentResponse.assessment).joinedload(Assessment.template)
        )
        .filter(
            StudentResponse.student_id == student_id,
            StudentResponse.completed_at.isnot(None)
        )
        .all()
    )
    
    # Group by assessment
    assessment_data = {}
    all_scores = []
    
    for response in responses:
        assessment_id = response.assessment_id
        if assessment_id not in assessment_data:
            # Fetch template for question details
            template = response.assessment.template
            questions_map = {q['question_id']: q for q in template.questions}
            
            assessment_data[assessment_id] = {
                "assessment_id": assessment_id,
                "template_name": template.name,
                "category": template.category,
                "title": response.assessment.title,
                "total_score": 0.0,
                "completed_at": response.completed_at,
                "responses": []
            }
        
        # Add response details
        question_info = questions_map.get(response.question_id, {})
        assessment_data[assessment_id]["responses"].append({
            "question_id": response.question_id,
            "question_text": response.question_text,
            "question_type": question_info.get('question_type'),
            "answer": response.answer,
            "score": response.score
        })
        assessment_data[assessment_id]["total_score"] += response.score or 0.0
    
    # Collect all total scores for overall statistics
    all_scores = [data["total_score"] for data in assessment_data.values()]
    overall_stats = calculate_statistics(all_scores)
    
    return success_response({
        "student_id": student.user_id,
        "student_name": student.display_name,
        "total_assessments": len(assessment_data),
        "overall_statistics": {
            "average_score": overall_stats["mean"],
            "min_score": overall_stats["min"],
            "max_score": overall_stats["max"],
            "median_score": overall_stats["median"],
            "std_dev": overall_stats["std_dev"]
        },
        "assessments": list(assessment_data.values())
    })

@router.get("/results/assessment/{assessment_id}/student/{student_id}")
async def get_student_assessment_result(
    assessment_id: UUID,
    student_id: UUID,
    db: Session = Depends(get_db)
):
    """Get one student's result for one specific assessment"""
    assessment = get_or_404(
        db, Assessment,
        Assessment.assessment_id == assessment_id,
        "Assessment not found"
    )
    
    student = get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    responses = (
        db.query(StudentResponse)
        .filter(
            StudentResponse.assessment_id == assessment_id,
            StudentResponse.student_id == student_id,
            StudentResponse.completed_at.isnot(None)
        )
        .all()
    )

    if not responses:
        raise HTTPException(status_code=404, detail="No completed assessment found for this student")

    # Fetch template for question details
    template = db.query(AssessmentTemplate).filter(
        AssessmentTemplate.template_id == assessment.template_id
    ).first()
    
    questions_map = {q['question_id']: q for q in template.questions}
    
    total_score = 0.0
    response_details = []
    for response in responses:
        question_info = questions_map.get(response.question_id, {})
        response_details.append({
            "question_id": response.question_id,
            "question_text": response.question_text,
            "question_type": question_info.get('question_type'),
            "answer": response.answer,
            "score": response.score
        })
        total_score += response.score or 0.0

    return success_response({
        "assessment_id": assessment_id,
        "student_id": student_id,
        "student_name": student.display_name,
        "template_name": template.name,
        "category": template.category,
        "title": assessment.title,
        "total_score": total_score,
        "completed_at": responses[0].completed_at if responses else None,
        "responses": response_details
    })

@router.get("/results/assessment/{assessment_id}/all")
async def get_assessment_all_students(
    assessment_id: UUID,
    db: Session = Depends(get_db)
):
    """Get all students' results for one assessment with comprehensive statistics"""
    assessment = get_or_404(
        db, Assessment,
        Assessment.assessment_id == assessment_id,
        "Assessment not found"
    )
    
    # Get all student responses for this assessment
    responses = (
        db.query(StudentResponse)
        .filter(
            StudentResponse.assessment_id == assessment_id,
            StudentResponse.completed_at.isnot(None)
        )
        .all()
    )
    
    if not responses:
        return success_response({
            "assessment_id": assessment_id,
            "template_name": assessment.template.name,
            "title": assessment.title,
            "total_students": 0,
            "statistics": {
                "average_score": None,
                "min_score": None,
                "max_score": None,
                "median_score": None,
                "std_dev": None
            },
            "student_results": []
        })
    
    # Group by student
    student_data = {}
    for response in responses:
        if response.student_id not in student_data:
            student = get_student_by_id(db, response.student_id)
            student_name = student.display_name if student else "Unknown"
            student_data[response.student_id] = {
                "student_id": response.student_id,
                "student_name": student_name,
                "total_score": 0.0,
                "completed_at": response.completed_at,
                "responses": []
            }
        
        student_data[response.student_id]["total_score"] += response.score or 0.0
        student_data[response.student_id]["responses"].append({
            "question_id": response.question_id,
            "question_text": response.question_text,
            "answer": response.answer,
            "score": response.score
        })
    
    # Calculate comprehensive statistics
    total_scores = [data["total_score"] for data in student_data.values()]
    stats = calculate_statistics(total_scores)
    
    # Calculate percentiles (25th, 50th/median, 75th)
    percentiles = {}
    if total_scores:
        sorted_scores = sorted(total_scores)
        percentiles = {
            "25th_percentile": round(statistics.quantiles(sorted_scores, n=4)[0], 2) if len(sorted_scores) >= 4 else None,
            "50th_percentile": stats["median"],
            "75th_percentile": round(statistics.quantiles(sorted_scores, n=4)[2], 2) if len(sorted_scores) >= 4 else None
        }
    
    return success_response({
        "assessment_id": assessment_id,
        "template_name": assessment.template.name,
        "category": assessment.template.category,
        "title": assessment.title,
        "school_id": assessment.school_id,
        "class_id": assessment.class_id,
        "total_students": len(student_data),
        "statistics": {
            "average_score": stats["mean"],
            "min_score": stats["min"],
            "max_score": stats["max"],
            "median_score": stats["median"],
            "std_dev": stats["std_dev"],
            "percentiles": percentiles
        },
        "student_results": list(student_data.values())
    })
