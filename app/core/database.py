from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Optimized database engine with connection pooling
# Note: Neon uses pooled connections, so we use smaller pool sizes
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,  # Smaller pool for Neon pooled connections
    max_overflow=5,  # Additional connections when pool is full
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False,  # Set to True for SQL debugging
    connect_args={
        "connect_timeout": 10,  # Connection timeout in seconds
        # Note: statement_timeout not supported in Neon pooled connections
        # Use unpooled connection string or set timeout at query level
    }
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Prevent lazy loading after commit
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Activity Database - uses separate DATABASE_URL_ACTIVITY if configured
activity_db_url = settings.DATABASE_URL_ACTIVITY or settings.DATABASE_URL

activity_engine = create_engine(
    activity_db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=5,
    pool_recycle=3600,
    echo=False,
    connect_args={
        "connect_timeout": 10,
    }
)

ActivitySessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=activity_engine,
    expire_on_commit=False
)

def get_activity_db():
    """Get database session for activities (uses separate DB if configured)."""
    db = ActivitySessionLocal()
    try:
        yield db
    finally:
        db.close()


# Auth Database - uses DATABASE_URL_AUTH for centralized authentication
auth_engine = create_engine(
    settings.DATABASE_URL_AUTH,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=5,
    pool_recycle=3600,
    echo=False,
    connect_args={
        "connect_timeout": 10,
    }
)

AuthSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=auth_engine,
    expire_on_commit=False
)

def get_auth_db():
    """Get database session for authentication (uses admin platform DB)."""
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()

