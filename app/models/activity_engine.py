"""
Model for reading activities from the activity engine's table.
This is a read-only model to fetch activity details.
"""
from sqlalchemy import Column, String, Text
from app.models.base import Base


class ActivityEngine(Base):
    """Read-only model for activities table from activity engine."""
    __tablename__ = "activities"
    
    activity_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    activity_type = Column(String)
