from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt, ExpiredSignatureError
from app.core.config import settings

def verify_password(plain_password: str, stored_password: str) -> bool:
    """Compare passwords directly without hashing (for development only)"""
    return plain_password == stored_password

def get_password_hash(password: str) -> str:
    """Return password as-is without hashing (for development only)"""
    return password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Dictionary containing user data (sub, user_id, etc.)
        expires_delta: Token expiration time (defaults to ACCESS_TOKEN_EXPIRE_MINUTES from settings)
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),  # Issued at
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT refresh token with longer expiration.
    
    Args:
        data: Dictionary containing user data (sub, user_id, etc.)
        expires_delta: Token expiration time (defaults to 7 days)
    
    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Refresh tokens last 7 days by default
        expire = datetime.utcnow() + timedelta(days=7)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate JWT access token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload or None if invalid/expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Verify token type
        if payload.get("type") != "access":
            return None
            
        return payload
    except ExpiredSignatureError:
        # Token has expired
        return None
    except JWTError:
        return None

def decode_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate JWT refresh token.
    
    Args:
        token: JWT refresh token string
    
    Returns:
        Decoded token payload or None if invalid/expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Verify token type
        if payload.get("type") != "refresh":
            return None
            
        return payload
    except ExpiredSignatureError:
        # Token has expired
        return None
    except JWTError:
        return None

def get_token_expiration(token: str) -> Optional[datetime]:
    """
    Get expiration time from token without full validation.
    
    Args:
        token: JWT token string
    
    Returns:
        Expiration datetime or None if invalid
    """
    try:
        # Decode without verification to get expiration
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False}
        )
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            return datetime.utcfromtimestamp(exp_timestamp)
        return None
    except JWTError:
        return None

def is_token_expired(token: str) -> bool:
    """
    Check if token is expired without full validation.
    
    Args:
        token: JWT token string
    
    Returns:
        True if expired, False otherwise
    """
    exp_time = get_token_expiration(token)
    if not exp_time:
        return True
    return datetime.utcnow() > exp_time
