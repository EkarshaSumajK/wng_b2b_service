from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from app.core.config import settings
from app.api.v1 import api_router
from fastapi.staticfiles import StaticFiles
import os

# Import logging components (Loguru-based, auto-initializes on import)
from app.core.logging_config import get_logger
from app.core.logging_middleware import LoggingMiddleware

# Get logger for this module
logger = get_logger(__name__)

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)
os.makedirs("logs", exist_ok=True)  # Create logs directory


app = FastAPI(
    title="School Mental Health Platform API",
    description="B2B SaaS platform for K-12 school mental health management",
    version="1.0.0"
)

# Custom CORS middleware that handles preflight properly
@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    # Handle preflight OPTIONS requests
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "600",
            }
        )
    
    # Process the actual request
    response = await call_next(request)
    
    # Add CORS headers to all responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

# Gzip Compression Middleware - compress responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add Logging Middleware
app.add_middleware(LoggingMiddleware)

app.include_router(api_router, prefix="/api/v1")

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.on_event("startup")
async def startup_event():
    """Application startup event handler."""
    logger.info("=" * 60)
    logger.info("Application starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Log Level: {settings.LOG_LEVEL}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler."""
    logger.info("=" * 60)
    logger.info("Application shutting down...")
    logger.info("=" * 60)


@app.get("/")
async def root():
    logger.debug("Root endpoint accessed")
    return {"message": "School Mental Health Platform API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health_check():
    logger.debug("Health check endpoint accessed")
    return {"status": "healthy"}

