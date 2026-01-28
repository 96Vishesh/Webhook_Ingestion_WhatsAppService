"""Tests for the GET /messages endpoint."""
import json
import pytest
from .conftest import compute_signature


def insert_message(client, message_id: str, from_: str, to: str, ts: str, text: str = None):
    """Helper to insert a message via webhook."""
    payload = {
        "message_id": message_id,
        "from": from_,
        "to": to,
        "ts": ts
    }
    if text is not None:
        payload["text"] = text
    
    body = json.dumps(payload).encode()
    sig = compute_signature(body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": sig}
    )
    assert response.status_code == 200


class TestMessagesBasicListing:
    """Tests for basic message listing."""
    
    def test_empty_database_returns_empty_list(self, client):
        """Empty database should return empty data array."""
        response = client.get("/messages")
        assert response.status_code == 200
        
        data = response.json()
        assert data["data"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0
    
    def test_list_messages_returns_all(self, client):
        """Should return all messages."""
        # Insert test messages
        insert_message(client, "m1", "+919876543210", "+14155550100", "2025-01-15T10:00:00Z", "Hello")
        insert_message(client, "m2", "+919876543211", "+14155550101", "2025-01-15T11:00:00Z", "World")
        
        response = client.get("/messages")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 2
        assert len(data["data"]) == 2
    
    def test_ordering_by_ts_and_message_id(self, client):
        """Messages should be ordered by ts ASC, message_id ASC."""
        # Insert messages out of order
        insert_message(client, "m3", "+919876543210", "+14155550100", "2025-01-15T12:00:00Z", "Third")
        insert_message(client, "m1", "+919876543210", "+14155550100", "2025-01-15T10:00:00Z", "First")
        insert_message(client, "m2a", "+919876543210", "+14155550100", "2025-01-15T11:00:00Z", "Second A")
        insert_message(client, "m2b", "+919876543210", "+14155550100", "2025-01-15T11:00:00Z", "Second B")
        
        response = client.get("/messages")
        data = response.json()["data"]
        
        # Check order: m1 (10:00), m2a (11:00), m2b (11:00), m3 (12:00)
        assert data[0]["message_id"] == "m1"
        assert data[1]["message_id"] == "m2a"
        assert data[2]["message_id"] == "m2b"
        assert data[3]["message_id"] == "m3"


class TestMessagesPagination:
    """Tests for message pagination."""
    
    def test_limit_parameter(self, client):
        """limit parameter should restrict number of results."""
        for i in range(5):
            insert_message(client, f"m{i}", "+919876543210", "+14155550100", f"2025-01-15T1{i}:00:00Z")
        
        response = client.get("/messages?limit=2")
        data = response.json()
        
        assert len(data["data"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
    
    def test_offset_parameter(self, client):
        """offset parameter should skip results."""
        for i in range(5):
            insert_message(client, f"msg{i}", "+919876543210", "+14155550100", f"2025-01-15T1{i}:00:00Z")
        
        response = client.get("/messages?offset=2&limit=2")
        data = response.json()
        
        assert len(data["data"]) == 2
        assert data["offset"] == 2
        assert data["data"][0]["message_id"] == "msg2"
    
    def test_limit_max_100(self, client):
        """limit should be capped at 100."""
        response = client.get("/messages?limit=150")
        assert response.status_code == 422  # Validation error
    
    def test_limit_min_1(self, client):
        """limit should be at least 1."""
        response = client.get("/messages?limit=0")
        assert response.status_code == 422
    
    def test_offset_min_0(self, client):
        """offset should be at least 0."""
        response = client.get("/messages?offset=-1")
        assert response.status_code == 422
    
    def test_default_limit_50(self, client):
        """Default limit should be 50."""
        response = client.get("/messages")
        assert response.json()["limit"] == 50


class TestMessagesFilters:
    """Tests for message filtering."""
    
    def test_filter_by_from(self, client):
        """from filter should match exactly."""
        insert_message(client, "m1", "+919876543210", "+14155550100", "2025-01-15T10:00:00Z")
        insert_message(client, "m2", "+919876543211", "+14155550100", "2025-01-15T11:00:00Z")
        insert_message(client, "m3", "+919876543210", "+14155550100", "2025-01-15T12:00:00Z")
        
        response = client.get("/messages?from=%2B919876543210")  # URL encoded +
        data = response.json()
        
        assert data["total"] == 2
        assert all(m["from"] == "+919876543210" for m in data["data"])
    
    def test_filter_by_since(self, client):
        """since filter should return messages >= timestamp."""
        insert_message(client, "m1", "+919876543210", "+14155550100", "2025-01-15T09:00:00Z")
        insert_message(client, "m2", "+919876543210", "+14155550100", "2025-01-15T10:00:00Z")
        insert_message(client, "m3", "+919876543210", "+14155550100", "2025-01-15T11:00:00Z")
        
        response = client.get("/messages?since=2025-01-15T10:00:00Z")
        data = response.json()
        
        assert data["total"] == 2
        assert data["data"][0]["message_id"] == "m2"
    
    def test_filter_by_q_text_search(self, client):
        """q filter should search in text field."""
        insert_message(client, "m1", "+919876543210", "+14155550100", "2025-01-15T10:00:00Z", "Hello world")
        insert_message(client, "m2", "+919876543210", "+14155550100", "2025-01-15T11:00:00Z", "Goodbye")
        insert_message(client, "m3", "+919876543210", "+14155550100", "2025-01-15T12:00:00Z", "hello again")
        
        response = client.get("/messages?q=hello")
        data = response.json()
        
        assert data["total"] == 2
    
    def test_combined_filters(self, client):
        """Multiple filters should be AND-ed together."""
        insert_message(client, "m1", "+919876543210", "+14155550100", "2025-01-15T09:00:00Z", "Hello")
        insert_message(client, "m2", "+919876543210", "+14155550100", "2025-01-15T11:00:00Z", "Hello")
        insert_message(client, "m3", "+919876543211", "+14155550100", "2025-01-15T12:00:00Z", "Hello")
        
        response = client.get("/messages?from=%2B919876543210&since=2025-01-15T10:00:00Z&q=Hello")
        data = response.json()
        
        assert data["total"] == 1
        assert data["data"][0]["message_id"] == "m2"
    
    def test_total_reflects_filters(self, client):
        """total should reflect filtered count, not total rows."""
        for i in range(10):
            sender = "+919876543210" if i < 7 else "+919876543211"
            insert_message(client, f"m{i}", sender, "+14155550100", f"2025-01-15T1{i}:00:00Z")
        
        response = client.get("/messages?from=%2B919876543210&limit=2")
        data = response.json()
        
        assert data["total"] == 7  # Filtered total
        assert len(data["data"]) == 2  # Limited results
