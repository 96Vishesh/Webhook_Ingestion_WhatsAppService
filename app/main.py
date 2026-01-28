import hmac
import hashlib
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Response, Query, HTTPException, Header
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError

from .config import get_settings
from .models import (
    WebhookMessage,
    WebhookResponse,
    ErrorResponse,
    MessageOut,
    MessagesListResponse,
    SenderCount,
    StatsResponse,
    HealthResponse,
)
from .storage import init_storage, get_storage
from .logging_utils import (
    setup_logging,
    get_logger,
    generate_request_id,
    set_request_context,
    clear_request_context,
    log_request,
    log_error,
)
from .metrics import get_metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan for startup/shutdown."""
    # Startup
    setup_logging()
    logger = get_logger()
    
    settings = get_settings()
    
    if not settings.webhook_secret:
        logger.warning("WEBHOOK_SECRET not set - readiness check will fail")
    
    # Initialize database
    try:
        init_storage()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    yield
    
    # Shutdown
    logger.info("Application shutting down")


app = FastAPI(
    title="WhatsApp Webhook Service",
    description="Production-style FastAPI service for WhatsApp-like message ingestion",
    version="1.0.0",
    lifespan=lifespan
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Middleware for request logging, metrics, and context."""
    start_time = time.time()
    request_id = generate_request_id()
    
    # Set request context
    set_request_context(request_id, request.method, request.url.path)
    
    # Store request_id for later use
    request.state.request_id = request_id
    request.state.start_time = start_time
    
    # Process request
    response = await call_next(request)
    
    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000
    
    # Record metrics
    metrics = get_metrics()
    metrics.inc_http_requests(request.url.path, response.status_code)
    metrics.observe_latency(latency_ms)
    
    # Log request (unless it's a webhook - that logs separately with extra fields)
    if request.url.path != "/webhook":
        log_request(response.status_code, latency_ms)
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    
    # Clear context
    clear_request_context()
    
    return response


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook", response_model=WebhookResponse)
async def webhook(request: Request, x_signature: Optional[str] = Header(None, alias="X-Signature")):
    """
    Ingest inbound WhatsApp-like messages.
    
    - Validates HMAC-SHA256 signature
    - Validates message payload
    - Inserts message idempotently
    """
    start_time = request.state.start_time
    settings = get_settings()
    metrics = get_metrics()
    
    # Read raw body for signature verification
    body = await request.body()
    
    # Default values for logging
    message_id = None
    dup = False
    result = None
    status_code = 200
    
    try:
        # Check if WEBHOOK_SECRET is set
        if not settings.webhook_secret:
            result = "server_error"
            status_code = 503
            log_error("WEBHOOK_SECRET not configured")
            metrics.inc_webhook_requests(result)
            latency_ms = (time.time() - start_time) * 1000
            log_request(status_code, latency_ms, message_id, dup, result)
            return JSONResponse(
                status_code=status_code,
                content={"detail": "server not ready"}
            )
        
        # Verify signature
        if not x_signature or not verify_signature(body, x_signature, settings.webhook_secret):
            result = "invalid_signature"
            status_code = 401
            log_error("Invalid or missing signature")
            metrics.inc_webhook_requests(result)
            latency_ms = (time.time() - start_time) * 1000
            log_request(status_code, latency_ms, message_id, dup, result)
            return JSONResponse(
                status_code=status_code,
                content={"detail": "invalid signature"}
            )
        
        # Parse and validate payload
        try:
            import json
            payload = json.loads(body)
            message = WebhookMessage(**payload)
            message_id = message.message_id
        except (json.JSONDecodeError, ValidationError) as e:
            result = "validation_error"
            status_code = 422
            metrics.inc_webhook_requests(result)
            latency_ms = (time.time() - start_time) * 1000
            log_request(status_code, latency_ms, message_id, dup, result)
            
            if isinstance(e, json.JSONDecodeError):
                return JSONResponse(
                    status_code=status_code,
                    content={"detail": "Invalid JSON"}
                )
            else:
                # Convert Pydantic errors to JSON-serializable format
                errors = [
                    {
                        "loc": list(err.get("loc", [])),
                        "msg": err.get("msg", ""),
                        "type": err.get("type", "")
                    }
                    for err in e.errors()
                ]
                return JSONResponse(
                    status_code=status_code,
                    content={"detail": errors}
                )
        
        # Insert message
        storage = get_storage()
        success, is_dup = storage.insert_message(
            message_id=message.message_id,
            from_msisdn=message.from_,
            to_msisdn=message.to,
            ts=message.ts,
            text=message.text
        )
        
        dup = is_dup
        result = "duplicate" if is_dup else "created"
        metrics.inc_webhook_requests(result)
        
        latency_ms = (time.time() - start_time) * 1000
        log_request(status_code, latency_ms, message_id, dup, result)
        
        return WebhookResponse(status="ok")
    
    except Exception as e:
        result = "server_error"
        status_code = 500
        log_error(f"Unexpected error: {str(e)}")
        metrics.inc_webhook_requests(result)
        latency_ms = (time.time() - start_time) * 1000
        log_request(status_code, latency_ms, message_id, dup, result)
        return JSONResponse(
            status_code=status_code,
            content={"detail": "internal server error"}
        )


@app.get("/messages", response_model=MessagesListResponse)
async def get_messages(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    from_: Optional[str] = Query(default=None, alias="from"),
    since: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None)
):
    """
    List stored messages with pagination and filters.
    
    - Ordered by ts ASC, message_id ASC
    - Supports from, since, and q (text search) filters
    """
    storage = get_storage()
    messages, total = storage.get_messages(
        limit=limit,
        offset=offset,
        from_filter=from_,
        since=since,
        q=q
    )
    
    return MessagesListResponse(
        data=[MessageOut(**m) for m in messages],
        total=total,
        limit=limit,
        offset=offset
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Provide simple message-level analytics.
    
    - Total messages
    - Unique senders count
    - Top 10 senders
    - First/last message timestamps
    """
    storage = get_storage()
    stats = storage.get_stats()
    
    return StatsResponse(
        total_messages=stats["total_messages"],
        senders_count=stats["senders_count"],
        messages_per_sender=[SenderCount(**s) for s in stats["messages_per_sender"]],
        first_message_ts=stats["first_message_ts"],
        last_message_ts=stats["last_message_ts"]
    )


@app.get("/health/live", response_model=HealthResponse)
async def health_live():
    """Liveness probe - always returns 200 if app is running."""
    return HealthResponse(status="ok")


@app.get("/health/ready", response_model=HealthResponse)
async def health_ready():
    """
    Readiness probe.
    
    Returns 200 only if:
    - DB is reachable and schema is applied
    - WEBHOOK_SECRET is set
    """
    settings = get_settings()
    storage = get_storage()
    
    if not settings.is_ready():
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "WEBHOOK_SECRET not set"}
        )
    
    if not storage.is_ready():
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "database not ready"}
        )
    
    return HealthResponse(status="ok")


@app.get("/metrics")
async def get_metrics_endpoint():
    """Expose Prometheus-style metrics."""
    metrics = get_metrics()
    return PlainTextResponse(
        content=metrics.format_prometheus(),
        media_type="text/plain"
    )