"""Tests for the POST /webhook endpoint."""
import json
import pytest
from .conftest import compute_signature


class TestWebhookValidSignature:
    """Tests for webhook with valid signatures."""
    
    def test_valid_message_creates_row(self, client):
        """Valid message with valid signature should be inserted."""
        body = json.dumps({
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello"
        }).encode()
        
        sig = compute_signature(body)
        response = client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": sig
            }
        )
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_duplicate_message_returns_200(self, client):
        """Duplicate message_id should return 200 (idempotent)."""
        body = json.dumps({
            "message_id": "m_dup",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello"
        }).encode()
        
        sig = compute_signature(body)
        headers = {"Content-Type": "application/json", "X-Signature": sig}
        
        # First request
        response1 = client.post("/webhook", content=body, headers=headers)
        assert response1.status_code == 200
        
        # Duplicate request
        response2 = client.post("/webhook", content=body, headers=headers)
        assert response2.status_code == 200
        assert response2.json() == {"status": "ok"}
        
        # Verify only one row exists
        msgs = client.get("/messages")
        assert len([m for m in msgs.json()["data"] if m["message_id"] == "m_dup"]) == 1
    
    def test_optional_text_field(self, client):
        """Message without text field should be valid."""
        body = json.dumps({
            "message_id": "m_no_text",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z"
        }).encode()
        
        sig = compute_signature(body)
        response = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Signature": sig}
        )
        
        assert response.status_code == 200


class TestWebhookInvalidSignature:
    """Tests for webhook with invalid/missing signatures."""
    
    def test_missing_signature_returns_401(self, client):
        """Missing X-Signature header should return 401."""
        body = json.dumps({
            "message_id": "m2",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello"
        }).encode()
        
        response = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 401
        assert response.json() == {"detail": "invalid signature"}
    
    def test_invalid_signature_returns_401(self, client):
        """Invalid X-Signature should return 401."""
        body = json.dumps({
            "message_id": "m3",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello"
        }).encode()
        
        response = client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": "invalid123"
            }
        )
        
        assert response.status_code == 401
        assert response.json() == {"detail": "invalid signature"}


class TestWebhookValidation:
    """Tests for webhook payload validation."""
    
    def test_empty_message_id_returns_422(self, client):
        """Empty message_id should return 422."""
        body = json.dumps({
            "message_id": "",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z"
        }).encode()
        
        sig = compute_signature(body)
        response = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Signature": sig}
        )
        
        assert response.status_code == 422
    
    def test_invalid_from_format_returns_422(self, client):
        """from field not in E.164 format should return 422."""
        body = json.dumps({
            "message_id": "m_invalid_from",
            "from": "9876543210",  # Missing +
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z"
        }).encode()
        
        sig = compute_signature(body)
        response = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Signature": sig}
        )
        
        assert response.status_code == 422
    
    def test_invalid_to_format_returns_422(self, client):
        """to field not in E.164 format should return 422."""
        body = json.dumps({
            "message_id": "m_invalid_to",
            "from": "+919876543210",
            "to": "14155550100",  # Missing +
            "ts": "2025-01-15T10:00:00Z"
        }).encode()
        
        sig = compute_signature(body)
        response = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Signature": sig}
        )
        
        assert response.status_code == 422
    
    def test_invalid_ts_format_returns_422(self, client):
        """ts field not in ISO-8601 UTC format should return 422."""
        body = json.dumps({
            "message_id": "m_invalid_ts",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15 10:00:00"  # Not ISO-8601 UTC
        }).encode()
        
        sig = compute_signature(body)
        response = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Signature": sig}
        )
        
        assert response.status_code == 422
    
    def test_text_too_long_returns_422(self, client):
        """text field exceeding 4096 characters should return 422."""
        body = json.dumps({
            "message_id": "m_long_text",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "x" * 4097
        }).encode()
        
        sig = compute_signature(body)
        response = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Signature": sig}
        )
        
        assert response.status_code == 422
    
    def test_invalid_json_returns_422(self, client):
        """Invalid JSON body should return 422."""
        body = b"not valid json"
        
        sig = compute_signature(body)
        response = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Signature": sig}
        )
        
        assert response.status_code == 422
