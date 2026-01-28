"""
Configuration module - 12-factor environment variable loading.
"""
import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment variables."""
    
    def __init__(self):
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:////data/app.db")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
        self.webhook_secret: str | None = os.getenv("WEBHOOK_SECRET")
    
    @property
    def db_path(self) -> str:
        """Extract the SQLite file path from DATABASE_URL."""
        # Handle sqlite:////data/app.db format
        url = self.database_url
        if url.startswith("sqlite:///"):
            return url[10:]  # Remove "sqlite:///"
        return url
    
    def is_ready(self) -> bool:
        """Check if all required configuration is present."""
        return bool(self.webhook_secret)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()