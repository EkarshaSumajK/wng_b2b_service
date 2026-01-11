"""
Logging Middleware for FastAPI

Provides comprehensive request/response logging including:
- Request ID generation and tracking
- Request/Response timing
- Error logging with full context
- Sensitive data masking
"""

import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException

from app.core.logging_config import (
    get_logger,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    log_api_request,
)

logger = get_logger(__name__)

# Headers and fields to mask for security
SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key", "api-key"}
SENSITIVE_FIELDS = {"password", "token", "secret", "api_key", "access_token"}


def mask_sensitive_data(data: dict) -> dict:
    """Mask sensitive fields in a dictionary."""
    masked = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS:
            masked[key] = "***MASKED***"
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_data(value)
        else:
            masked[key] = value
    return masked


def get_client_ip(request: Request) -> str:
    """Get the real client IP, considering proxy headers."""
    # Check for X-Forwarded-For header (common in reverse proxy setups)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check for X-Real-IP header
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging all HTTP requests and responses.
    
    Features:
    - Generates unique correlation ID for tracking
    - Logs request details (method, path, query params)
    - Logs response status and timing
    - Logs errors with full context
    - Masks sensitive data in logs
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate and set correlation ID
        correlation_id = request.headers.get("x-request-id") or set_correlation_id()
        if request.headers.get("x-request-id"):
            set_correlation_id(correlation_id)
        
        # Store correlation ID in request state for access in endpoints
        request.state.request_id = correlation_id
        
        # Capture request details
        start_time = time.perf_counter()
        client_ip = get_client_ip(request)
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        
        # Mask sensitive query params
        masked_query = mask_sensitive_data(query_params) if query_params else {}
        
        # Log request start
        logger.info(
            f"Request started: {method} {path}",
            request_id=correlation_id,
            method=method,
            path=path,
            query_params=masked_query,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent", "unknown")[:100],
        )
        
        # Process request
        response = None
        error_detail = None
        
        try:
            response = await call_next(request)
            
        except HTTPException as exc:
            # Log HTTP exceptions (client errors, etc.)
            error_detail = str(exc.detail)
            logger.warning(
                f"HTTP exception: {method} {path} - {exc.status_code}",
                request_id=correlation_id,
                status_code=exc.status_code,
                detail=error_detail,
            )
            raise
            
        except Exception as exc:
            # Log unexpected errors
            error_detail = str(exc)
            logger.error(
                f"Unhandled exception: {method} {path}",
                request_id=correlation_id,
                error_type=type(exc).__name__,
                error_message=error_detail,
            )
            raise
            
        finally:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log request completion
            status_code = response.status_code if response else 500
            
            if status_code < 400:
                logger.info(
                    f"Request completed: {method} {path} - {status_code} ({duration_ms:.2f}ms)",
                    request_id=correlation_id,
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    client_ip=client_ip,
                )
            elif status_code < 500:
                logger.warning(
                    f"Request completed: {method} {path} - {status_code} ({duration_ms:.2f}ms)",
                    request_id=correlation_id,
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    client_ip=client_ip,
                )
            else:
                logger.error(
                    f"Request completed: {method} {path} - {status_code} ({duration_ms:.2f}ms)",
                    request_id=correlation_id,
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    client_ip=client_ip,
                )
            
            # Log slow requests
            if duration_ms > 1000:  # > 1 second
                logger.warning(
                    f"Slow request detected: {method} {path} took {duration_ms:.2f}ms",
                    request_id=correlation_id,
                    duration_ms=round(duration_ms, 2),
                )
            
            # Clear correlation ID after request
            clear_correlation_id()
        
        # Add request ID to response headers for client tracking
        if response:
            response.headers["X-Request-ID"] = correlation_id
            
        return response


class SQLLoggingMiddleware:
    """
    Optional middleware to log SQL queries.
    Enable this for debugging database performance issues.
    
    Usage:
        from sqlalchemy import event
        from app.core.database import engine
        
        SQLLoggingMiddleware.attach(engine)
    """
    
    @staticmethod
    def attach(engine):
        """Attach SQL logging to a SQLAlchemy engine."""
        from sqlalchemy import event
        import time
        
        sql_logger = get_logger("database.sql")
        
        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault("query_start_time", []).append(time.perf_counter())
            sql_logger.debug(
                f"SQL Query: {statement[:200]}{'...' if len(statement) > 200 else ''}"
            )
        
        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            query_times = conn.info.get("query_start_time", [])
            if query_times:
                start_time = query_times.pop()
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                if duration_ms > 100:  # Log slow queries (> 100ms)
                    sql_logger.warning(
                        f"Slow SQL Query ({duration_ms:.2f}ms): {statement[:100]}..."
                    )


def log_database_errors(logger_instance=None):
    """
    Decorator for database operations to log errors.
    
    Usage:
        @log_database_errors()
        async def get_students(db: Session):
            return db.query(Student).all()
    """
    import functools
    
    db_logger = logger_instance or get_logger("database")
    
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                db_logger.error(
                    f"Database error in {func.__name__}: {str(e)}"
                )
                raise
        
        @functools.wraps(func)        
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                db_logger.error(
                    f"Database error in {func.__name__}: {str(e)}"
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
