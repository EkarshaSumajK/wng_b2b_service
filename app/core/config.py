from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    DATABASE_URL_ACTIVITY: Optional[str] = None  # Separate DB for activities
    
    # Admin Platform Database (for centralized authentication)
    # SECURITY: This should be set via environment variable, not hardcoded
    DATABASE_URL_AUTH: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Environment
    ENVIRONMENT: str = "development"
    
    # Logging
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # AWS S3 Configuration
    AWS_S3_BUCKET: Optional[str] = None
    AWS_REGION: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
