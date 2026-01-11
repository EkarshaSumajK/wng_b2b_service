from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, and_
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import statistics

from app.core.database import get_db
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.models.assessment import Assessment, AssessmentTemplate, StudentResponse
from app.models.activity_assignment import ActivityAssignment, AssignmentStatus
from app.models.activity_submission import ActivitySubmission, SubmissionStatus
from app.models.activity import Activity
from app.models.activity_engine import ActivityEngine
from app.models.class_model import Class
from app.models.user import User, UserRole
from app.core.student_helpers import get_student_by_id, get_students_by_school, get_student_ids_by_school

logger = get_logger(__name__)
router = APIRouter()


# ============== HELPER FUNCTIONS ==============

def calculate_statistics(scores: List[float]) -> Dict[str, Any]:
    """Calculate comprehensive statistics for a list of scores"""
    if not scores:
        return {"min": None, "max": None, "mean": None, "median": None, "std_dev": None, "count": 0}
    
    return {
        "min": round(min(scores), 2),
        "max": round(max(scores), 2),
        "mean": round(statistics.mean(scores), 2),
        "median": round(statistics.median(scores), 2),
        "std_dev": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0.0,
        "count": len(scores)
    }


def calculate_percentiles(scores: List[float]) -> Dict[str, Any]:
    """Calculate percentiles for scores"""
    if len(scores) < 4:
        return {"25th": None, "50th": None, "75th": None}
    sorted_scores = sorted(scores)
    quantiles = statistics.quantiles(sorted_scores, n=4)
    return {
        "25th": round(quantiles[0], 2),
        "50th": round(quantiles[1], 2),
        "75th": round(quantiles[2], 2)
    }


# ============== ASSESSMENT ANALYTICS ==============

@router.get("/assessments/{assessment_id}")
async def get_assessment_analytics(
    assessment_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive analytics for a single assessment.
    
    Returns:
    - Overall statistics (mean, median, std_dev, percentiles)
    - Score distribution
    - Question-level analysis
    - Completion metrics
    - Student breakdown with scores
    """
    assessment = (
        db.query(Assessment)
        .options(joinedload(Assessment.template), joinedload(Assessment.class_obj))
        .filter(Assessment.assessment_id == assessment_id)
        .first()
    )
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Get all completed responses
    responses = (
        db.query(StudentResponse)
        .filter(
            StudentResponse.assessment_id == assessment_id,
            StudentResponse.completed_at.isnot(None)
        )
        .all()
    )
    
    # Group responses by student
    student_scores = {}
    question_scores = {}
    
    for response in responses:
        # Aggregate student scores
        if response.student_id not in student_scores:
            student_scores[response.student_id] = {"total": 0.0, "responses": []}
        student_scores[response.student_id]["total"] += response.score or 0.0
        student_scores[response.student_id]["responses"].append(response)
        
        # Aggregate question scores
        if response.question_id not in question_scores:
            question_scores[response.question_id] = {
                "question_text": response.question_text,
                "scores": []
            }
        if response.score is not None:
            question_scores[response.question_id]["scores"].append(response.score)
    
    # Calculate overall statistics
    total_scores = [data["total"] for data in student_scores.values()]
    overall_stats = calculate_statistics(total_scores)
    percentiles = calculate_percentiles(total_scores)
    
    # Score distribution (buckets)
    score_distribution = {"low": 0, "medium": 0, "high": 0}
    if total_scores:
        max_possible = len(assessment.template.questions) * 5  # Assuming max 5 per question
        for score in total_scores:
            ratio = score / max_possible if max_possible > 0 else 0
            if ratio < 0.33:
                score_distribution["low"] += 1
            elif ratio < 0.66:
                score_distribution["medium"] += 1
            else:
                score_distribution["high"] += 1
    
    # Question-level analysis
    question_analysis = []
    for q_id, q_data in question_scores.items():
        q_stats = calculate_statistics(q_data["scores"])
        question_analysis.append({
            "question_id": q_id,
            "question_text": q_data["question_text"],
            "response_count": len(q_data["scores"]),
            "average_score": q_stats["mean"],
            "min_score": q_stats["min"],
            "max_score": q_stats["max"]
        })
    
    # Get student details
    student_results = []
    for student_id, data in student_scores.items():
        student = get_student_by_id(db, student_id)
        if student:
            student_results.append({
                "student_id": student_id,
                "student_name": student.display_name,
                "total_score": round(data["total"], 2),
                "completed_at": data["responses"][0].completed_at if data["responses"] else None
            })
    
    # Sort by score descending
    student_results.sort(key=lambda x: x["total_score"], reverse=True)
    
    # Completion metrics
    total_expected = 0
    if assessment.class_id:
        # Count students in class from b2b_users with role=STUDENT
        total_expected = db.query(User).filter(
            User.role == UserRole.STUDENT,
            User.profile['class_id'].astext == str(assessment.class_id)
        ).count()
    
    return success_response({
        "assessment_id": assessment_id,
        "template_name": assessment.template.name,
        "category": assessment.template.category,
        "title": assessment.title,
        "class_name": assessment.class_obj.name if assessment.class_obj else None,
        "created_at": assessment.created_at,
        "completion_metrics": {
            "total_expected": total_expected,
            "total_completed": len(student_scores),
            "completion_rate": round(len(student_scores) / total_expected * 100, 1) if total_expected > 0 else 0
        },
        "overall_statistics": {
            **overall_stats,
            "percentiles": percentiles
        },
        "score_distribution": score_distribution,
        "question_analysis": question_analysis,
        "student_results": student_results
    })



@router.get("/students/{student_id}/assessments")
async def get_student_assessment_analytics(
    student_id: UUID,
    school_id: Optional[UUID] = None,
    category: Optional[str] = None,
    days: Optional[int] = Query(None, description="Filter to last N days"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive assessment analytics for a single student.
    
    Returns:
    - Overall performance across all assessments
    - Score trends over time
    - Category breakdown
    - Comparison to class/school averages
    - Individual assessment details
    """
    student = get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Build query for student responses
    query = (
        db.query(StudentResponse)
        .options(joinedload(StudentResponse.assessment).joinedload(Assessment.template))
        .filter(
            StudentResponse.student_id == student_id,
            StudentResponse.completed_at.isnot(None)
        )
    )
    
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(StudentResponse.completed_at >= cutoff)
    
    responses = query.all()
    
    # Group by assessment
    assessment_data = {}
    category_scores = {}
    
    for response in responses:
        assessment = response.assessment
        template = assessment.template
        
        # Filter by category if specified
        if category and template.category != category:
            continue
        
        # Filter by school if specified
        if school_id and assessment.school_id != school_id:
            continue
        
        a_id = assessment.assessment_id
        if a_id not in assessment_data:
            assessment_data[a_id] = {
                "assessment_id": a_id,
                "template_name": template.name,
                "category": template.category,
                "title": assessment.title,
                "completed_at": response.completed_at,
                "total_score": 0.0,
                "question_count": len(template.questions)
            }
        assessment_data[a_id]["total_score"] += response.score or 0.0
        
        # Track category scores
        cat = template.category or "uncategorized"
        if cat not in category_scores:
            category_scores[cat] = []
        category_scores[cat].append(response.score or 0.0)
    
    # Calculate overall statistics
    all_scores = [data["total_score"] for data in assessment_data.values()]
    overall_stats = calculate_statistics(all_scores)
    
    # Category breakdown
    category_breakdown = []
    for cat, scores in category_scores.items():
        category_breakdown.append({
            "category": cat,
            "assessment_count": len(set(a["assessment_id"] for a in assessment_data.values() if a.get("category") == cat)),
            "total_responses": len(scores),
            "average_score": round(statistics.mean(scores), 2) if scores else None
        })
    
    # Score trend (chronological)
    assessments_list = list(assessment_data.values())
    assessments_list.sort(key=lambda x: x["completed_at"] or datetime.min)
    
    score_trend = [
        {
            "date": a["completed_at"].isoformat() if a["completed_at"] else None,
            "assessment": a["template_name"],
            "score": round(a["total_score"], 2)
        }
        for a in assessments_list
    ]
    
    # Compare to class average (if student has a class)
    class_comparison = None
    student_class_id = student.profile.get("class_id") if student.profile else None
    if student_class_id:
        # Get all students in the same class from b2b_users
        classmates = db.query(User.user_id).filter(
            User.role == UserRole.STUDENT,
            User.profile['class_id'].astext == student_class_id,
            User.user_id != student_id
        ).all()
        classmate_ids = [c[0] for c in classmates]
        
        if classmate_ids:
            # Get their scores for the same assessments
            classmate_scores = []
            for a_id in assessment_data.keys():
                class_responses = (
                    db.query(func.sum(StudentResponse.score))
                    .filter(
                        StudentResponse.assessment_id == a_id,
                        StudentResponse.student_id.in_(classmate_ids),
                        StudentResponse.completed_at.isnot(None)
                    )
                    .group_by(StudentResponse.student_id)
                    .all()
                )
                classmate_scores.extend([r[0] for r in class_responses if r[0]])
            
            if classmate_scores:
                class_avg = statistics.mean(classmate_scores)
                student_avg = overall_stats["mean"] or 0
                class_comparison = {
                    "class_average": round(class_avg, 2),
                    "student_average": round(student_avg, 2),
                    "difference": round(student_avg - class_avg, 2),
                    "percentile_rank": None  # Could calculate if needed
                }
    
    return success_response({
        "student_id": student_id,
        "student_name": student.display_name,
        "class_id": student.profile.get("class_id") if student.profile else None,
        "total_assessments": len(assessment_data),
        "overall_statistics": overall_stats,
        "category_breakdown": category_breakdown,
        "score_trend": score_trend,
        "class_comparison": class_comparison,
        "assessments": [
            {
                "assessment_id": a["assessment_id"],
                "template_name": a["template_name"],
                "category": a["category"],
                "title": a["title"],
                "total_score": round(a["total_score"], 2),
                "completed_at": a["completed_at"]
            }
            for a in assessments_list
        ]
    })


# ============== ACTIVITY ANALYTICS ==============

@router.get("/activities/{activity_id}")
async def get_activity_analytics(
    activity_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive analytics for a single activity.
    
    Returns:
    - Activity details (matching fetch API format)
    - Assignment statistics
    - Submission metrics (completion rate, status breakdown)
    - Class-level breakdown
    - Time-based analysis
    """
    activity = db.query(ActivityEngine).filter(ActivityEngine.activity_id == str(activity_id)).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Get all assignments for this activity
    assignments = (
        db.query(ActivityAssignment)
        .options(joinedload(ActivityAssignment.class_obj))
        .filter(ActivityAssignment.activity_id == activity_id)
        .all()
    )
    
    # Build activity info matching fetch API format
    activity_info = {
        "activity_id": str(activity_id),
        "activity_name": activity.title,
        "description": activity.description,
        "type": activity.activity_type,
        "duration": None,
        "target_grades": None,
        "themes": None,
        "diagnosis": None,
        "objectives": None,
        "materials": None,
        "instructions": None,
        "location": None,
        "risk_level": None,
        "skill_level": None,
        "thumbnail_url": None,
        "is_counselor_only": False
    }
    
    if not assignments:
        return success_response({
            **activity_info,
            "total_assignments": 0,
            "submission_metrics": None,
            "class_breakdown": [],
            "status_distribution": {}
        })
    
    assignment_ids = [a.assignment_id for a in assignments]
    
    # Get all submissions for these assignments
    submissions = (
        db.query(ActivitySubmission)
        .filter(ActivitySubmission.assignment_id.in_(assignment_ids))
        .all()
    )
    
    # Status distribution
    status_counts = {"PENDING": 0, "SUBMITTED": 0, "VERIFIED": 0, "REJECTED": 0}
    for sub in submissions:
        status_counts[sub.status.value] = status_counts.get(sub.status.value, 0) + 1
    
    total_submissions = len(submissions)
    completed = status_counts["SUBMITTED"] + status_counts["VERIFIED"] + status_counts["REJECTED"]
    
    # Class-level breakdown
    class_breakdown = []
    for assignment in assignments:
        class_submissions = [s for s in submissions if s.assignment_id == assignment.assignment_id]
        class_completed = len([s for s in class_submissions if s.status != SubmissionStatus.PENDING])
        
        class_breakdown.append({
            "assignment_id": assignment.assignment_id,
            "class_id": assignment.class_id,
            "class_name": assignment.class_obj.name if assignment.class_obj else None,
            "assigned_at": assignment.created_at,
            "due_date": assignment.due_date,
            "total_students": len(class_submissions),
            "completed": class_completed,
            "completion_rate": round(class_completed / len(class_submissions) * 100, 1) if class_submissions else 0
        })
    
    # Time analysis - submissions over time
    submission_timeline = {}
    for sub in submissions:
        if sub.submitted_at:
            date_key = sub.submitted_at.date().isoformat()
            submission_timeline[date_key] = submission_timeline.get(date_key, 0) + 1
    
    return success_response({
        **activity_info,
        "total_assignments": len(assignments),
        "submission_metrics": {
            "total_expected": total_submissions,
            "total_completed": completed,
            "completion_rate": round(completed / total_submissions * 100, 1) if total_submissions > 0 else 0,
            "verified_count": status_counts["VERIFIED"],
            "pending_review": status_counts["SUBMITTED"]
        },
        "status_distribution": status_counts,
        "class_breakdown": class_breakdown,
        "submission_timeline": [
            {"date": k, "count": v} 
            for k, v in sorted(submission_timeline.items())
        ]
    })


@router.get("/students/{student_id}/activities")
async def get_student_activity_analytics(
    student_id: UUID,
    class_id: Optional[UUID] = None,
    status: Optional[str] = Query(None, description="Filter by status: PENDING, SUBMITTED, VERIFIED, REJECTED"),
    days: Optional[int] = Query(None, description="Filter to last N days"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive activity analytics for a single student.
    
    Returns:
    - Overall completion metrics
    - Status breakdown
    - Activity type distribution
    - Recent submissions with full activity details
    - Performance over time
    """
    student = get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Build query for submissions
    query = (
        db.query(ActivitySubmission)
        .options(
            joinedload(ActivitySubmission.assignment)
        )
        .filter(ActivitySubmission.student_id == student_id)
    )
    
    if status:
        try:
            status_enum = SubmissionStatus(status)
            query = query.filter(ActivitySubmission.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(ActivitySubmission.created_at >= cutoff)
    
    submissions = query.all()
    
    # Batch fetch activities
    activity_ids = [sub.assignment.activity_id for sub in submissions if sub.assignment]
    activities_map = {}
    if activity_ids:
        activities_data = db.query(ActivityEngine).filter(ActivityEngine.activity_id.in_(activity_ids)).all()
        activities_map = {str(a.activity_id): a for a in activities_data}
    
    # Status breakdown
    status_counts = {"PENDING": 0, "SUBMITTED": 0, "VERIFIED": 0, "REJECTED": 0}
    activity_types = {}
    themes_count = {}
    
    submission_details = []
    for sub in submissions:
        status_counts[sub.status.value] = status_counts.get(sub.status.value, 0) + 1
        
        activity = activities_map.get(str(sub.assignment.activity_id)) if sub.assignment else None
        if activity:
            act_type = activity.activity_type or "UNKNOWN"
            activity_types[act_type] = activity_types.get(act_type, 0) + 1
            
            submission_details.append({
                "submission_id": sub.submission_id,
                "activity": {
                    "activity_id": str(activity.activity_id),
                    "activity_name": activity.title,
                    "description": activity.description,
                    "type": act_type,
                    "duration": None,
                    "themes": None,
                    "diagnosis": None,
                    "objectives": None,
                    "location": None,
                    "risk_level": None,
                    "skill_level": None,
                    "thumbnail_url": None
                },
                "status": sub.status.value,
                "submitted_at": sub.submitted_at,
                "feedback": sub.feedback,
                "due_date": sub.assignment.due_date if sub.assignment else None,
                "assigned_at": sub.assignment.created_at if sub.assignment else None
            })
    
    total = len(submissions)
    completed = status_counts["SUBMITTED"] + status_counts["VERIFIED"] + status_counts["REJECTED"]
    
    # Sort by most recent
    submission_details.sort(key=lambda x: x["submitted_at"] or datetime.min, reverse=True)
    
    # Activity type distribution
    type_distribution = [
        {"type": k, "count": v, "percentage": round(v / total * 100, 1) if total > 0 else 0}
        for k, v in activity_types.items()
    ]
    
    # Theme distribution
    theme_distribution = [
        {"theme": k, "count": v}
        for k, v in sorted(themes_count.items(), key=lambda x: x[1], reverse=True)
    ]
    
    # Completion trend (by week)
    weekly_completion = {}
    for sub in submissions:
        if sub.submitted_at:
            week_start = sub.submitted_at - timedelta(days=sub.submitted_at.weekday())
            week_key = week_start.date().isoformat()
            weekly_completion[week_key] = weekly_completion.get(week_key, 0) + 1
    
    return success_response({
        "student_id": student_id,
        "student_name": student.display_name,
        "class_id": student.profile.get("class_id") if student.profile else None,
        "overall_metrics": {
            "total_assigned": total,
            "total_completed": completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "verified_count": status_counts["VERIFIED"],
            "rejected_count": status_counts["REJECTED"],
            "pending_count": status_counts["PENDING"]
        },
        "status_distribution": status_counts,
        "activity_type_distribution": type_distribution,
        "theme_distribution": theme_distribution,
        "weekly_completion_trend": [
            {"week_of": k, "completed": v}
            for k, v in sorted(weekly_completion.items())
        ],
        "recent_submissions": submission_details[:10]  # Last 10
    })


# ============== COMBINED/SUMMARY ANALYTICS ==============

@router.get("/students/{student_id}/summary")
async def get_student_summary_analytics(
    student_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get a combined summary of both assessment and activity analytics for a student.
    Useful for dashboard views.
    """
    student = get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Assessment summary
    assessment_responses = (
        db.query(StudentResponse)
        .filter(
            StudentResponse.student_id == student_id,
            StudentResponse.completed_at.isnot(None)
        )
        .all()
    )
    
    assessment_ids = set(r.assessment_id for r in assessment_responses)
    assessment_scores = {}
    for r in assessment_responses:
        if r.assessment_id not in assessment_scores:
            assessment_scores[r.assessment_id] = 0.0
        assessment_scores[r.assessment_id] += r.score or 0.0
    
    # Activity summary
    activity_submissions = (
        db.query(ActivitySubmission)
        .filter(ActivitySubmission.student_id == student_id)
        .all()
    )
    
    activity_status = {"PENDING": 0, "SUBMITTED": 0, "VERIFIED": 0, "REJECTED": 0}
    for sub in activity_submissions:
        activity_status[sub.status.value] = activity_status.get(sub.status.value, 0) + 1
    
    total_activities = len(activity_submissions)
    completed_activities = activity_status["SUBMITTED"] + activity_status["VERIFIED"] + activity_status["REJECTED"]
    
    return success_response({
        "student_id": student_id,
        "student_name": student.display_name,
        "class_id": student.profile.get("class_id") if student.profile else None,
        "risk_level": student.profile.get("risk_level") if student.profile else None,
        "wellbeing_score": student.profile.get("wellbeing_score") if student.profile else None,
        "assessments": {
            "total_completed": len(assessment_ids),
            "average_score": round(statistics.mean(assessment_scores.values()), 2) if assessment_scores else None,
            "last_assessment": max((r.completed_at for r in assessment_responses), default=None)
        },
        "activities": {
            "total_assigned": total_activities,
            "total_completed": completed_activities,
            "completion_rate": round(completed_activities / total_activities * 100, 1) if total_activities > 0 else 0,
            "status_breakdown": activity_status
        }
    })



# ============== ASSESSMENT MONITORING ==============

@router.get("/assessments/{assessment_id}/monitoring")
async def get_assessment_monitoring(
    assessment_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Monitor assessment completion and response consistency.
    
    Returns:
    - Expected vs actual responses per student
    - Students with incomplete responses
    - Students who haven't started
    - Response consistency check
    """
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
    
    # Get all students who should take this assessment (from b2b_users with role=STUDENT)
    expected_students = []
    if assessment.class_id:
        students_query = db.query(User).filter(
            User.role == UserRole.STUDENT,
            User.profile['class_id'].astext == str(assessment.class_id)
        )
        # Exclude students in exclusion list
        if assessment.excluded_students:
            students_query = students_query.filter(~User.user_id.in_(assessment.excluded_students))
        expected_students = students_query.all()
    
    expected_student_ids = {s.user_id for s in expected_students}
    
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
            "student_id": student.user_id,
            "student_name": student.display_name
        }
        
        if student.user_id not in student_responses:
            not_started_students.append(student_info)
        else:
            data = student_responses[student.user_id]
            answered_count = len(data["question_ids"])
            missing_questions = question_ids - data["question_ids"]
            extra_questions = data["question_ids"] - question_ids
            
            student_detail = {
                **student_info,
                "expected_questions": total_questions,
                "answered_questions": answered_count,
                "missing_questions": list(missing_questions),
                "extra_questions": list(extra_questions),  # Questions not in template
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
            student = get_student_by_id(db, student_id)
            if student:
                data = student_responses[student_id]
                unexpected_students.append({
                    "student_id": student_id,
                    "student_name": student.display_name,
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
            student = get_student_by_id(db, response.student_id)
            question_data[q_id]["responses"].append({
                "student_id": response.student_id,
                "student_name": student.display_name if student else "Unknown",
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


@router.get("/students/{student_id}/assessment-history")
async def get_student_assessment_history(
    student_id: UUID,
    include_responses: bool = Query(False, description="Include individual question responses"),
    db: Session = Depends(get_db)
):
    """
    Get complete assessment history for a student with response details.
    Shows exactly what questions were answered for each assessment.
    """
    student = get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get all responses grouped by assessment
    responses = (
        db.query(StudentResponse)
        .options(joinedload(StudentResponse.assessment).joinedload(Assessment.template))
        .filter(StudentResponse.student_id == student_id)
        .order_by(StudentResponse.completed_at.desc())
        .all()
    )
    
    # Group by assessment
    assessment_history = {}
    for response in responses:
        a_id = response.assessment_id
        if a_id not in assessment_history:
            assessment = response.assessment
            template = assessment.template
            assessment_history[a_id] = {
                "assessment_id": a_id,
                "template_name": template.name,
                "category": template.category,
                "title": assessment.title,
                "total_questions_in_template": len(template.questions),
                "questions_answered": 0,
                "total_score": 0.0,
                "completed_at": response.completed_at,
                "is_complete": False,
                "responses": [] if include_responses else None
            }
        
        assessment_history[a_id]["questions_answered"] += 1
        assessment_history[a_id]["total_score"] += response.score or 0.0
        
        if include_responses:
            assessment_history[a_id]["responses"].append({
                "question_id": response.question_id,
                "question_text": response.question_text,
                "answer": response.answer,
                "score": response.score
            })
    
    # Check completeness
    for a_id, data in assessment_history.items():
        data["is_complete"] = data["questions_answered"] == data["total_questions_in_template"]
        data["total_score"] = round(data["total_score"], 2)
    
    # Sort by date
    history_list = sorted(
        assessment_history.values(),
        key=lambda x: x["completed_at"] or datetime.min,
        reverse=True
    )
    
    return success_response({
        "student_id": student_id,
        "student_name": student.display_name,
        "total_assessments": len(history_list),
        "complete_assessments": len([a for a in history_list if a["is_complete"]]),
        "incomplete_assessments": len([a for a in history_list if not a["is_complete"]]),
        "assessment_history": history_list
    })
