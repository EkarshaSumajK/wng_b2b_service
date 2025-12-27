from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, union_all
from typing import List, Optional
from enum import Enum

from app.core.database import get_activity_db
from app.core.logging_config import get_logger
from app.models.activity_data import ActivityData, GeneratedActivityData
from app.core.s3_service import s3_service

# Initialize logger
logger = get_logger(__name__)

router = APIRouter()


class ActivitySource(str, Enum):
    ALL = "all"
    CURATED = "curated"
    GENERATED = "generated"


def _build_activity_response(activity, source: str, include_flashcards: bool = False):
    """Helper function to build activity response from either table."""
    activity_response = {
        # Database row columns
        "id": activity.id,
        "activity_id": activity.activity_id,
        "activity_name": activity.activity_name,
        "framework": activity.framework,
        "age": activity.age,
        "diagnosis": activity.diagnosis,
        "cognitive": activity.cognitive,
        "sensory": activity.sensory,
        "themes": activity.themes,
        "setting": activity.setting,
        "supervision": activity.supervision,
        "duration_pref": activity.duration_pref,
        "risk_level": activity.risk_level,
        "skill_level": activity.skill_level,
        
        # Raw activity_data JSONB - return as-is from database
        "activity_data": activity.activity_data,
        
        # Extracted thumbnail path from ID pattern
        "thumbnail_url": s3_service.generate_presigned_url(f"master/thumbnails/{activity.activity_id}.png"),
        
        # Source tracking
        "source": source,
        "flashcards": None
    }
    
    if include_flashcards:
        activity_response["flashcards"] = s3_service.fetch_flashcards(activity.activity_id)
    
    return activity_response


def _filter_by_themes(activities, theme_list: List[str], source: str, include_flashcards: bool = False):
    """Filter activities by themes and build response."""
    result = []
    for activity in activities:
        act_data = activity.activity_data or {}
        
        if theme_list:
            act_themes = act_data.get("Themes", [])
            act_themes_lower = " ".join([t.lower() for t in act_themes]) if isinstance(act_themes, list) else ""
            if not any(t in act_themes_lower for t in theme_list):
                continue
        
        result.append(_build_activity_response(activity, source, include_flashcards))
    
    return result


@router.get("/")
def get_activities(
    skip: int = 0,
    limit: int = 100,
    age: Optional[int] = Query(None, description="Filter by age"),
    diagnosis: Optional[str] = Query(None, description="Filter by diagnosis (e.g., ADHD, Anxiety)"),
    themes: Optional[str] = Query(None, description="Filter by themes (comma-separated)"),
    source: ActivitySource = Query(ActivitySource.ALL, description="Filter by source: all, curated, or generated"),
    include_flashcards: bool = Query(False, description="Include S3 flashcard images in response"),
    db: Session = Depends(get_activity_db)
):
    """
    Get all activities with optional filtering.
    
    Filters:
    - age: Filter by exact age
    - diagnosis: Filter by diagnosis (case-insensitive partial match)
    - themes: Filter by themes (comma-separated, e.g., "Emotional Regulation,Motor Skills")
    - source: Filter by source (all, curated, generated)
    - include_flashcards: If true, includes base64 flashcard images from S3
    """
    logger.debug(
        "Fetching activities",
        extra={"extra_data": {"age": age, "diagnosis": diagnosis, "themes": themes, "source": source, "skip": skip, "limit": limit}}
    )
    
    theme_list = [t.strip().lower() for t in themes.split(",")] if themes else []
    result = []
    
    # Query curated activities
    if source in [ActivitySource.ALL, ActivitySource.CURATED]:
        curated_query = db.query(ActivityData)
        if age is not None:
            curated_query = curated_query.filter(ActivityData.age == age)
        if diagnosis:
            curated_query = curated_query.filter(ActivityData.diagnosis.ilike(f"%{diagnosis}%"))
        
        curated_activities = curated_query.all()
        logger.debug(f"Found {len(curated_activities)} curated activities")
        result.extend(_filter_by_themes(curated_activities, theme_list, "curated", include_flashcards))
    
    # Query generated activities
    if source in [ActivitySource.ALL, ActivitySource.GENERATED]:
        generated_query = db.query(GeneratedActivityData)
        if age is not None:
            generated_query = generated_query.filter(GeneratedActivityData.age == age)
        if diagnosis:
            generated_query = generated_query.filter(GeneratedActivityData.diagnosis.ilike(f"%{diagnosis}%"))
        
        generated_activities = generated_query.all()
        logger.debug(f"Found {len(generated_activities)} generated activities")
        result.extend(_filter_by_themes(generated_activities, theme_list, "generated", include_flashcards))
    
    # Apply pagination after combining
    total_count = len(result)
    result = result[skip:skip + limit]
    
    return {
        "filters": {
            "age": age,
            "diagnosis": diagnosis,
            "themes": theme_list if theme_list else None,
            "source": source.value
        },
        "total_count": total_count,
        "count": len(result),
        "activities": result
    }


@router.get("/{activity_id}")
def get_activity(
    activity_id: str, 
    include_flashcards: bool = Query(False, description="Include S3 flashcard images"),
    db: Session = Depends(get_activity_db)
):
    """Get a specific activity by ID (searches both curated and generated activities)"""
    logger.debug(f"Fetching activity: {activity_id}")
    
    # First try curated activities
    activity = db.query(ActivityData).filter(ActivityData.activity_id == activity_id).first()
    source = "curated"
    
    # If not found, try generated activities
    if not activity:
        activity = db.query(GeneratedActivityData).filter(GeneratedActivityData.activity_id == activity_id).first()
        source = "generated"
    
    if not activity:
        logger.warning(f"Activity not found: {activity_id}")
        raise HTTPException(status_code=404, detail="Activity not found")
    
    return _build_activity_response(activity, source, include_flashcards)



