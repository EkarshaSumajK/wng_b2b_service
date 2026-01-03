from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from typing import Optional

from app.core.database import get_db
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token
)
from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.user import User
from pydantic import BaseModel, EmailStr

# Initialize logger for this module
logger = get_logger(__name__)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int  # Access token expiration in seconds
    user: dict


class UserInfo(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: str
    school_id: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login endpoint - returns JWT token
    Authenticates against b2b_users table
    """
    logger.info(f"Login attempt for email: {login_data.email}")
    
    # Find user by email in b2b_users table
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user:
        logger.warning(f"Login failed - user not found: {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not user.hashed_password or not verify_password(login_data.password, user.hashed_password):
        logger.warning(
            f"Login failed - invalid password for user: {login_data.email}",
            extra={"extra_data": {"user_id": str(user.user_id)}}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login time
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # Create token data
    token_data = {
        "sub": user.email,
        "user_id": str(user.user_id),
        "role": user.role.value if user.role else "USER",
        "school_id": str(user.school_id) if user.school_id else None
    }
    
    # Create access token (short-lived: 30 minutes)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    
    # Create refresh token (long-lived: 7 days)
    refresh_token_expires = timedelta(days=7)
    refresh_token = create_refresh_token(
        data=token_data,
        expires_delta=refresh_token_expires
    )
    
    logger.info(
        f"Login successful for user: {login_data.email}",
        extra={
            "extra_data": {
                "user_id": str(user.user_id),
                "role": user.role.value if user.role else None,
                "school_id": str(user.school_id) if user.school_id else None
            }
        }
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        "user": {
            "user_id": str(user.user_id),
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role.value if user.role else "USER",
            "school_id": str(user.school_id) if user.school_id else None
        }
    }


@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 compatible token login (for Swagger UI)
    Authenticates against b2b_users table
    """
    logger.debug(f"Token login attempt for: {form_data.username}")
    
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not user.hashed_password or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Token login failed for: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login time
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # Create token data
    token_data = {
        "sub": user.email,
        "user_id": str(user.user_id),
        "role": user.role.value if user.role else "USER",
        "school_id": str(user.school_id) if user.school_id else None
    }
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    
    logger.info(f"Token login successful for: {form_data.username}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Get current user information from token
    """
    from app.api.dependencies import get_current_user
    
    logger.debug("Fetching current user info from token")
    
    user = await get_current_user(token, db)
    
    logger.debug(
        f"Retrieved user info for: {user.email}",
        extra={"extra_data": {"user_id": str(user.user_id)}}
    )
    
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value if user.role else "USER",
        "school_id": str(user.school_id) if user.school_id else None
    }


@router.post("/logout")
async def logout():
    """
    Logout endpoint (client should delete token)
    """
    logger.info("User logout requested")
    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    Returns a new access token while keeping the same refresh token valid.
    The refresh token should be stored securely and reused until it expires (7 days).
    """
    logger.debug("Token refresh attempt")
    
    # Decode and validate refresh token
    payload = decode_refresh_token(refresh_data.refresh_token)
    
    if not payload:
        logger.warning("Token refresh failed - invalid or expired refresh token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user identifier
    user_id_str = payload.get("user_id")
    if not user_id_str:
        logger.warning("Token refresh failed - missing user ID in token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify user still exists
    from uuid import UUID
    try:
        user_uuid = UUID(user_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.user_id == user_uuid).first()
    
    if not user:
        logger.warning(f"Token refresh failed - user not found: {user_id_str}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create new access token with same data
    token_data = {
        "sub": user.email,
        "user_id": str(user.user_id),
        "role": user.role.value if user.role else "USER",
        "school_id": str(user.school_id) if user.school_id else None
    }
    
    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    
    logger.info(
        f"Token refresh successful for user: {user.email}",
        extra={"extra_data": {"user_id": str(user.user_id)}}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    }
