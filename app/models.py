import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# E.164 phone number pattern: + followed by digits only
E164_PATTERN = re.compile(r"^\+\d+$")

# ISO-8601 UTC pattern with Z suffix
ISO8601_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class WebhookMessage(BaseModel):
    message_id: str = Field(..., min_length=1)
    from_: str = Field(..., alias="from")
    to: str
    ts: str
    text: Optional[str] = Field(None, max_length=4096)
    
    @field_validator("from_", "to")
    @classmethod
    def validate_e164(cls, v: str, info) -> str:
        if not E164_PATTERN.match(v):
            field_name = "from" if info.field_name == "from_" else info.field_name
            raise ValueError(f"{field_name} must be in E.164 format (start with +, then digits only)")
        return v
    
    @field_validator("ts")
    @classmethod
    def validate_iso8601_utc(cls, v: str) -> str:
        """Validate ISO-8601 UTC timestamp with Z suffix."""
        if not ISO8601_UTC_PATTERN.match(v):
            raise ValueError("ts must be ISO-8601 UTC format with Z suffix (e.g., 2025-01-15T10:00:00Z)")
        # Also verify it's a valid datetime
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("ts must be a valid datetime")
        return v
    
    model_config = {
        "populate_by_name": True
    }


class WebhookResponse(BaseModel):
    """Response for successful webhook processing."""
    status: str = "ok"


class ErrorResponse(BaseModel):
    """Error response."""
    detail: str


class MessageOut(BaseModel):
    """Message output for listing."""
    message_id: str
    from_: str = Field(..., serialization_alias="from")
    to: str
    ts: str
    text: Optional[str] = None
    
    model_config = {
        "populate_by_name": True
    }


class MessagesListResponse(BaseModel):
    """Response for /messages endpoint."""
    data: list[MessageOut]
    total: int
    limit: int
    offset: int


class SenderCount(BaseModel):
    """Sender message count for stats."""
    from_: str = Field(..., serialization_alias="from")
    count: int
    
    model_config = {
        "populate_by_name": True
    }


class StatsResponse(BaseModel):
    """Response for /stats endpoint."""
    total_messages: int
    senders_count: int
    messages_per_sender: list[SenderCount]
    first_message_ts: Optional[str] = None
    last_message_ts: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str