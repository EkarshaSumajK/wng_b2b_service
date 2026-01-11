"""
Structured logging service using Loguru with request correlation IDs and environment-specific configuration.

This service provides:
- Structured JSON logging for production environments
- Request correlation ID tracking
- Different log levels per environment
- Error tracking and metrics
- Performance monitoring capabilities
"""

import json
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional, Union

from loguru import logger
from pydantic import BaseModel
from rich.console import Console
from rich.text import Text

from app.core.config import settings

# Context variable for request correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class LogConfig(BaseModel):
    """Configuration for logging setup."""

    level: str = "INFO"
    format_json: bool = True
    enable_file_logging: bool = True
    log_file_path: str = "logs/app.log"
    max_file_size: str = "50 MB"
    retention: str = "7 days"
    enable_error_file: bool = True
    error_file_path: str = "logs/error.log"


class StructuredLogger:
    """
    Structured logging service with correlation ID support and environment-specific configuration.
    """

    def __init__(self):
        self._configured = False
        self._config = self._get_log_config()
        self._console = Console()
        self._setup_logging()

    def _get_log_config(self) -> LogConfig:
        """Get logging configuration based on environment."""
        config = LogConfig()

        # Environment-specific settings
        environment = getattr(settings, "ENVIRONMENT", "development")
        log_level = getattr(settings, "LOG_LEVEL", "INFO")
        
        if environment == "development":
            config.level = log_level
            config.format_json = False
            config.enable_file_logging = True
        elif environment == "production":
            config.level = "INFO"
            config.format_json = True
            config.enable_file_logging = True
        elif environment == "test":
            config.level = "DEBUG"
            config.format_json = False
            config.enable_file_logging = False

        return config

    def _rich_console_formatter(self, record) -> str:
        """Rich-based console formatter with simplified format and color coding."""
        # Extract information from loguru record
        filename = record["name"]
        line_number = record["line"]
        message = record["message"]
        level = record["level"].name

        # Color coding for different log levels
        level_colors = {
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }

        color = level_colors.get(level, "white")

        # Create the formatted string directly with Rich console
        # Format: filename | line_number | message
        text = Text()
        text.append(filename, style="blue")
        text.append(" | ", style="white")
        text.append(str(line_number), style="magenta")
        text.append(" | ", style="white")
        text.append(message, style=color)

        # Use Rich console to render without extra newlines
        with self._console.capture() as capture:
            self._console.print(text, end="")

        return capture.get() + "\n"

    def _setup_logging(self) -> None:
        """Configure Loguru logging based on environment."""
        if self._configured:
            return

        # Remove default handler
        logger.remove()

        # Always use Rich-based simplified console formatter for console output
        logger.add(
            sys.stdout,
            format=self._rich_console_formatter,
            level=self._config.level,
            serialize=False,
            filter=self._add_correlation_id,
        )

        # Add file logging if enabled
        if self._config.enable_file_logging:
            # Create logs directory
            log_path = Path(self._config.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # General log file - maintain detailed format for file logging
            file_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | correlation_id={extra[correlation_id]} | {message}"
            logger.add(
                self._config.log_file_path,
                format=file_format,
                level=self._config.level,
                rotation=self._config.max_file_size,
                retention=self._config.retention,
                serialize=self._config.format_json,
                filter=self._add_correlation_id,
                enqueue=True,  # Thread-safe logging
            )

            # Error-only log file
            if self._config.enable_error_file:
                error_path = Path(self._config.error_file_path)
                error_path.parent.mkdir(parents=True, exist_ok=True)

                error_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | correlation_id={extra[correlation_id]} | {message}"
                logger.add(
                    self._config.error_file_path,
                    format=error_format,
                    level="ERROR",
                    rotation=self._config.max_file_size,
                    retention=self._config.retention,
                    serialize=self._config.format_json,
                    filter=self._add_correlation_id,
                    enqueue=True,
                )

        self._configured = True

    def _add_correlation_id(self, record: Dict[str, Any]) -> bool:
        """Add correlation ID to log record."""
        environment = getattr(settings, "ENVIRONMENT", "development")
        record["extra"]["correlation_id"] = correlation_id.get() or "none"
        record["extra"]["environment"] = environment
        return True

    def _json_formatter(self, record: Dict[str, Any]) -> str:
        """Custom JSON formatter for structured logging."""
        environment = getattr(settings, "ENVIRONMENT", "development")
        log_entry = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
            "correlation_id": record["extra"].get("correlation_id", "none"),
            "environment": record["extra"].get("environment", environment),
        }

        # Add exception info if present
        if record.get("exception"):
            log_entry["exception"] = {
                "type": record["exception"].type.__name__,
                "message": str(record["exception"].value),
                "traceback": record["exception"].traceback,
            }

        # Add any extra fields
        for key, value in record["extra"].items():
            if key not in ["correlation_id", "environment"]:
                log_entry[key] = value

        return json.dumps(log_entry, default=str) + "\n"

    def set_correlation_id(self, cid: Optional[str] = None) -> str:
        """Set correlation ID for request tracking."""
        if cid is None:
            cid = str(uuid.uuid4())
        correlation_id.set(cid)
        return cid

    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID."""
        return correlation_id.get()

    def clear_correlation_id(self) -> None:
        """Clear correlation ID."""
        correlation_id.set(None)

    def bind_context(self, **kwargs: Any) -> "logger":
        """Bind additional context to the logger."""
        return logger.bind(**kwargs)

    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        **extra_data: Any
    ) -> None:
        """Log performance metrics."""
        pass

    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[str] = None,
        **extra_data: Any
    ) -> None:
        """Log API request details."""
        logger.info(
            "API request",
            http_method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            **extra_data
        )

    def log_database_query(
        self,
        query_type: str,
        table: str,
        duration_ms: float,
        rows_affected: Optional[int] = None,
        **extra_data: Any
    ) -> None:
        """Log database query performance."""
        logger.debug(
            "Database query",
            query_type=query_type,
            table=table,
            duration_ms=duration_ms,
            rows_affected=rows_affected,
            **extra_data
        )

    def log_external_api_call(
        self,
        service: str,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        success: bool = True,
        **extra_data: Any
    ) -> None:
        """Log external API call details."""
        logger.info(
            "External API call",
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            success=success,
            **extra_data
        )


# Global logger instance
structured_logger = StructuredLogger()


# Export commonly used methods for convenience
def get_logger(name: Optional[str] = None):
    """Get the configured logger instance."""
    return logger


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set correlation ID for request tracking."""
    return structured_logger.set_correlation_id(cid)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return structured_logger.get_correlation_id()


def clear_correlation_id() -> None:
    """Clear correlation ID."""
    structured_logger.clear_correlation_id()


def log_performance(
    operation: str, duration_ms: float, success: bool = True, **extra: Any
) -> None:
    """Log performance metrics."""
    structured_logger.log_performance(operation, duration_ms, success, **extra)


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None,
    **extra: Any
) -> None:
    """Log API request details."""
    structured_logger.log_api_request(
        method, path, status_code, duration_ms, user_id, **extra
    )


def log_database_query(
    query_type: str,
    table: str,
    duration_ms: float,
    rows_affected: Optional[int] = None,
    **extra: Any
) -> None:
    """Log database query performance."""
    structured_logger.log_database_query(
        query_type, table, duration_ms, rows_affected, **extra
    )


def log_external_api_call(
    service: str,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    success: bool = True,
    **extra: Any
) -> None:
    """Log external API call details."""
    structured_logger.log_external_api_call(
        service, endpoint, method, status_code, duration_ms, success, **extra
    )


# Backward compatibility aliases
def generate_request_id() -> str:
    """Generate a unique request ID (alias for set_correlation_id)."""
    return set_correlation_id()


def set_request_id(request_id: str) -> None:
    """Set the request ID for the current context (alias for set_correlation_id)."""
    correlation_id.set(request_id)


def get_request_id() -> str:
    """Get the current request ID (alias for get_correlation_id)."""
    return correlation_id.get() or ""
