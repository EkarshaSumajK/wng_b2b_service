from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from token.
    Supports tokens from both b2b_service and admin platform.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    payload = decode_access_token(token)
    if not payload:
        raise exc
    
    # Admin platform tokens use 'sub' as user_id string
    # B2B tokens may use 'user_id' directly
    user_id_str = payload.get("sub") or payload.get("user_id")
    
    if user_id_str:
        try:
            user_id = UUID(user_id_str)
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                return user
        except (ValueError, AttributeError):
            pass
    
    # Fallback: try to get by email
    email = payload.get("email")
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            return user
    
    raise exc

# Optional dependency - returns None if not authenticated
async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not token:
        return None
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None

# Alias for backward compatibility
async def get_current_b2b_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Alias for get_current_user - backward compatibility."""
    return await get_current_user(token, db)

# Alias for backward compatibility
async def get_current_b2b_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Alias for get_current_user_optional - backward compatibility."""
    return await get_current_user_optional(token, db)
