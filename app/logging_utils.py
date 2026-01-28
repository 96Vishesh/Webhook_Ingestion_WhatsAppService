import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

from .config import get_settings


# Context variables for request-scoped data
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
method_var: ContextVar[str] = ContextVar("method", default="")
path_var: ContextVar[str] = ContextVar("path", default="")


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add request context if available
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id
        
        method = method_var.get()
        if method:
            log_data["method"] = method
        
        path = path_var.get()
        if path:
            log_data["path"] = path
        
        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data)


def setup_logging() -> logging.Logger:
    """Set up the JSON logger."""
    settings = get_settings()
    
    logger = logging.getLogger("app")
    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Add JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
    
    return logger


def get_logger() -> logging.Logger:
    """Get the application logger."""
    return logging.getLogger("app")


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())[:8]


def set_request_context(request_id: str, method: str, path: str) -> None:
    """Set the request context for logging."""
    request_id_var.set(request_id)
    method_var.set(method)
    path_var.set(path)


def clear_request_context() -> None:
    """Clear the request context."""
    request_id_var.set("")
    method_var.set("")
    path_var.set("")


def log_request(
    status: int,
    latency_ms: float,
    message_id: Optional[str] = None,
    dup: Optional[bool] = None,
    result: Optional[str] = None
) -> None:
    """Log a request with all required fields."""
    logger = get_logger()
    
    extra_fields: dict[str, Any] = {
        "status": status,
        "latency_ms": round(latency_ms, 2)
    }
    
    # Add webhook-specific fields
    if message_id is not None:
        extra_fields["message_id"] = message_id
    if dup is not None:
        extra_fields["dup"] = dup
    if result is not None:
        extra_fields["result"] = result
    
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="",
        lno=0,
        msg="request completed",
        args=(),
        exc_info=None
    )
    record.extra_fields = extra_fields
    logger.handle(record)


def log_error(message: str, **extra: Any) -> None:
    """Log an error with extra fields."""
    logger = get_logger()
    record = logger.makeRecord(
        name=logger.name,
        level=logging.ERROR,
        fn="",
        lno=0,
        msg=message,
        args=(),
        exc_info=None
    )
    record.extra_fields = extra
    logger.handle(record)