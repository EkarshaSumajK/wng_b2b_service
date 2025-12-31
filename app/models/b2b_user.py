from sqlalchemy import Column, String, Boolean, Integer, DateTime, Date, UUID, text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from app.core.database import Base

class B2BUser(Base):
    """
    B2BUser model mapping to b2b_users table in the admin platform database.
    This table stores authentication and user profile information.
    """
    __tablename__ = "b2b_users"
    
    # Primary key
    b2b_user_id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("uuid_generate_v4()")
    )
    
    # User identification
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=False)
    
    # Authentication fields
    password_hash = Column(String(255), nullable=True)
    auth_method = Column(String(20), nullable=True, default='otp')
    is_verified = Column(Boolean, default=False)
    
    # Profile information
    profile_image_id = Column(UUID(as_uuid=True), nullable=True)
    profile_picture = Column(String, nullable=True)
    
    # Organizational fields (NEW - storing role and school_id)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # Links to users table
    school_id = Column(UUID(as_uuid=True), nullable=True)
    role = Column(String, nullable=True)
    
    # Activity tracking
    enrollment_date = Column(Date, server_default=text("CURRENT_DATE"))
    is_active = Column(Boolean, default=True)
    total_points = Column(Integer, default=0)
    last_login_at = Column(DateTime, nullable=True)
    
    # Metadata (renamed to avoid SQLAlchemy reserved word)
    user_metadata = Column('metadata', JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<B2BUser(b2b_user_id={self.b2b_user_id}, email={self.email}, name={self.name}, role={self.role})>"

