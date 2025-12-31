from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from app.core.database import get_db, get_auth_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.b2b_user import B2BUser

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db)
) -> User:
    """
    Get current user - backward compatibility layer.
    Authenticates using B2BUser system but returns the linked User model.
    """
    # 1. Validation via B2B System
    b2b_user = await get_current_b2b_user(token, auth_db)
    
    # 2. Check for linked User profile
    if not b2b_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not fully linked to application profile",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 3. Fetch Legacy User Object
    user = db.query(User).filter(User.user_id == b2b_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    return user

# Optional dependency - returns None if not authenticated
async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db)
) -> Optional[User]:
    if not token:
        return None
    try:
        return await get_current_user(token, db, auth_db)
    except HTTPException:
        return None

# B2B User authentication (using admin platform database)
async def get_current_b2b_user(token: str = Depends(oauth2_scheme), auth_db: Session = Depends(get_auth_db)) -> B2BUser:
    """
    Get current B2B user from the admin platform database (b2b_users table).
    This is the primary authentication method.
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    payload = decode_access_token(token)
    if not payload:
        raise exc
    
    # First try to get b2b_user_id
    b2b_user_id_str = payload.get("b2b_user_id")
    if b2b_user_id_str:
        try:
            b2b_user_id = UUID(b2b_user_id_str)
            b2b_user = auth_db.query(B2BUser).filter(B2BUser.b2b_user_id == b2b_user_id).first()
            if b2b_user:
                return b2b_user
        except (ValueError, AttributeError):
            pass
    
    # Fallback: try to get by email
    email = payload.get("sub")
    if email:
        b2b_user = auth_db.query(B2BUser).filter(B2BUser.email == email).first()
        if b2b_user:
            return b2b_user
    
    raise exc

# Optional B2B user dependency - returns None if not authenticated
async def get_current_b2b_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    auth_db: Session = Depends(get_auth_db)
) -> Optional[B2BUser]:
    """
    Optional B2B user dependency - returns None if not authenticated.
    """
    if not token:
        return None
    try:
        return await get_current_b2b_user(token, auth_db)
    except HTTPException:
        return None
