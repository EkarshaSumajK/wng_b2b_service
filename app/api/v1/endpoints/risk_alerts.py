from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID

from app.api.dependencies import get_db
from app.core.response import success_response
from app.core.logging_config import get_logger
from app.core.student_helpers import get_student_ids_by_school, get_student_name
from app.models.risk_alert import RiskAlert, AlertStatus, AlertLevel
from app.models.user import User, UserRole
from app.schemas.risk_alert import RiskAlert as RiskAlertSchema, RiskAlertCreate, RiskAlertUpdate

# Initialize logger
logger = get_logger(__name__)

router = APIRouter()


@router.get("")
def get_risk_alerts(
    skip: int = 0,
    limit: int = 100,
    school_id: Optional[UUID] = Query(None),
    student_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    assigned_to: Optional[UUID] = Query(None),
    db: Session = Depends(get_db)
):
    """Get all risk alerts with optional filtering"""
    logger.debug("Listing risk alerts", extra={"extra_data": {"school_id": str(school_id) if school_id else None, "student_id": str(student_id) if student_id else None, "level": level}})
    query = db.query(RiskAlert).options(
        joinedload(RiskAlert.student),
        joinedload(RiskAlert.assigned_user)
    )
    
    # Filter by school if provided
    if school_id:
        student_ids = get_student_ids_by_school(db, school_id)
        query = query.filter(RiskAlert.student_id.in_(student_ids))
    
    if student_id:
        query = query.filter(RiskAlert.student_id == student_id)
    if status:
        query = query.filter(RiskAlert.status == status.upper())
    if level:
        query = query.filter(RiskAlert.level == level.upper())
    if assigned_to:
        query = query.filter(RiskAlert.assigned_to == assigned_to)
    
    alerts = query.order_by(RiskAlert.created_at.desc()).offset(skip).limit(limit).all()
    logger.debug(f"Found {len(alerts)} risk alerts")
    
    # Build response using eager-loaded relationships
    result = []
    for alert in alerts:
        # Get student name from User model
        student_name = "Unknown"
        if alert.student:
            student_name = alert.student.display_name or "Unknown"
        
        result.append({
            "id": str(alert.alert_id),
            "studentId": str(alert.student_id),
            "studentName": student_name,
            "level": alert.level.value.lower(),
            "type": alert.type.value.lower(),
            "description": alert.description,
            "triggers": alert.triggers or [],
            "recommendations": alert.recommendations or [],
            "assignedTo": alert.assigned_user.display_name if alert.assigned_user else "Unassigned",
            "assignedToId": str(alert.assigned_to) if alert.assigned_to else None,
            "status": alert.status.value.lower().replace('_', '-'),
            "createdAt": alert.created_at.isoformat(),
            "updatedAt": alert.updated_at.isoformat() if alert.updated_at else None
        })
    
    return success_response(result)


@router.get("/{alert_id}", response_model=RiskAlertSchema)
def get_risk_alert(alert_id: UUID, db: Session = Depends(get_db)):
    """Get a specific risk alert by ID"""
    logger.debug(f"Fetching risk alert: {alert_id}")
    alert = db.query(RiskAlert).filter(RiskAlert.alert_id == alert_id).first()
    if not alert:
        logger.warning(f"Risk alert not found: {alert_id}")
        raise HTTPException(status_code=404, detail="Risk alert not found")
    return alert


@router.post("", response_model=RiskAlertSchema, status_code=201)
def create_risk_alert(alert: RiskAlertCreate, db: Session = Depends(get_db)):
    """Create a new risk alert"""
    logger.info("Creating risk alert", extra={"extra_data": {"student_id": str(alert.student_id) if hasattr(alert, 'student_id') else None}})
    db_alert = RiskAlert(**alert.model_dump())
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    logger.info(f"Risk alert created", extra={"extra_data": {"alert_id": str(db_alert.alert_id)}})
    return db_alert


@router.put("/{alert_id}", response_model=RiskAlertSchema)
def update_risk_alert(alert_id: UUID, alert: RiskAlertUpdate, db: Session = Depends(get_db)):
    """Update a risk alert"""
    logger.info(f"Updating risk alert: {alert_id}")
    db_alert = db.query(RiskAlert).filter(RiskAlert.alert_id == alert_id).first()
    if not db_alert:
        logger.warning(f"Risk alert update failed - not found: {alert_id}")
        raise HTTPException(status_code=404, detail="Risk alert not found")
    
    for key, value in alert.model_dump(exclude_unset=True).items():
        setattr(db_alert, key, value)
    
    db.commit()
    db.refresh(db_alert)
    logger.info(f"Risk alert updated", extra={"extra_data": {"alert_id": str(alert_id)}})
    return db_alert


@router.delete("/{alert_id}", status_code=204)
def delete_risk_alert(alert_id: UUID, db: Session = Depends(get_db)):
    """Delete a risk alert"""
    logger.info(f"Deleting risk alert: {alert_id}")
    db_alert = db.query(RiskAlert).filter(RiskAlert.alert_id == alert_id).first()
    if not db_alert:
        logger.warning(f"Risk alert deletion failed - not found: {alert_id}")
        raise HTTPException(status_code=404, detail="Risk alert not found")
    
    db.delete(db_alert)
    db.commit()
    logger.info(f"Risk alert deleted", extra={"extra_data": {"alert_id": str(alert_id)}})
    return None
