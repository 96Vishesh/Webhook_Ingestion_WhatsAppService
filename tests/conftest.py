"""Test configuration and fixtures."""
import os
import sys
import tempfile

import pytest

# Set test environment variables before importing app
os.environ["WEBHOOK_SECRET"] = "testsecret"


@pytest.fixture(scope="function")
def test_db():
    """Create a temporary database for testing."""
    # Create temp file
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Set environment variable
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    
    # Reset storage singleton
    from app import storage
    storage._storage = None
    
    # Initialize database
    storage.init_storage()
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass
    
    storage._storage = None


@pytest.fixture
def client(test_db):
    """Create a test client."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    return TestClient(app)


def compute_signature(body: bytes, secret: str = "testsecret") -> str:
    """Compute HMAC-SHA256 signature for testing."""
    import hmac
    import hashlib
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
