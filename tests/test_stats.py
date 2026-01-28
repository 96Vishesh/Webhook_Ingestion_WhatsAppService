"""Tests for the GET /stats endpoint."""
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


class TestStatsEndpoint:
    """Tests for the /stats endpoint."""
    
    def test_empty_database_stats(self, client):
        """Empty database should return zero stats."""
        response = client.get("/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_messages"] == 0
        assert data["senders_count"] == 0
        assert data["messages_per_sender"] == []
        assert data["first_message_ts"] is None
        assert data["last_message_ts"] is None
    
    def test_total_messages_count(self, client):
        """total_messages should count all messages."""
        for i in range(5):
            insert_message(client, f"m{i}", "+919876543210", "+14155550100", f"2025-01-15T1{i}:00:00Z")
        
        response = client.get("/stats")
        data = response.json()
        
        assert data["total_messages"] == 5
    
    def test_senders_count(self, client):
        """senders_count should count unique senders."""
        insert_message(client, "m1", "+919876543210", "+14155550100", "2025-01-15T10:00:00Z")
        insert_message(client, "m2", "+919876543211", "+14155550100", "2025-01-15T11:00:00Z")
        insert_message(client, "m3", "+919876543210", "+14155550100", "2025-01-15T12:00:00Z")
        insert_message(client, "m4", "+919876543212", "+14155550100", "2025-01-15T13:00:00Z")
        
        response = client.get("/stats")
        data = response.json()
        
        assert data["senders_count"] == 3
    
    def test_messages_per_sender_sorted_by_count(self, client):
        """messages_per_sender should be sorted by count DESC."""
        # Sender A: 3 messages
        for i in range(3):
            insert_message(client, f"ma{i}", "+919876543210", "+14155550100", f"2025-01-15T10:0{i}:00Z")
        
        # Sender B: 5 messages
        for i in range(5):
            insert_message(client, f"mb{i}", "+919876543211", "+14155550100", f"2025-01-15T11:0{i}:00Z")
        
        # Sender C: 1 message
        insert_message(client, "mc0", "+919876543212", "+14155550100", "2025-01-15T12:00:00Z")
        
        response = client.get("/stats")
        data = response.json()
        
        senders = data["messages_per_sender"]
        assert len(senders) == 3
        assert senders[0]["from"] == "+919876543211"
        assert senders[0]["count"] == 5
        assert senders[1]["from"] == "+919876543210"
        assert senders[1]["count"] == 3
        assert senders[2]["from"] == "+919876543212"
        assert senders[2]["count"] == 1
    
    def test_messages_per_sender_limited_to_10(self, client):
        """messages_per_sender should return at most 10 senders."""
        # Create 15 different senders
        for i in range(15):
            insert_message(client, f"m{i}", f"+9198765432{i:02d}", "+14155550100", f"2025-01-15T{i:02d}:00:00Z")
        
        response = client.get("/stats")
        data = response.json()
        
        assert len(data["messages_per_sender"]) <= 10
    
    def test_first_and_last_message_timestamps(self, client):
        """first/last message timestamps should be correct."""
        insert_message(client, "m2", "+919876543210", "+14155550100", "2025-01-15T12:00:00Z")
        insert_message(client, "m1", "+919876543210", "+14155550100", "2025-01-10T09:00:00Z")  # Earliest
        insert_message(client, "m3", "+919876543210", "+14155550100", "2025-01-20T15:00:00Z")  # Latest
        
        response = client.get("/stats")
        data = response.json()
        
        assert data["first_message_ts"] == "2025-01-10T09:00:00Z"
        assert data["last_message_ts"] == "2025-01-20T15:00:00Z"
    
    def test_messages_per_sender_sum_equals_total(self, client):
        """Sum of messages_per_sender counts should equal total_messages."""
        insert_message(client, "m1", "+919876543210", "+14155550100", "2025-01-15T10:00:00Z")
        insert_message(client, "m2", "+919876543210", "+14155550100", "2025-01-15T11:00:00Z")
        insert_message(client, "m3", "+919876543211", "+14155550100", "2025-01-15T12:00:00Z")
        
        response = client.get("/stats")
        data = response.json()
        
        sum_counts = sum(s["count"] for s in data["messages_per_sender"])
        assert sum_counts == data["total_messages"]
