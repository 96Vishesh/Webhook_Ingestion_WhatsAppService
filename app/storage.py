import sqlite3
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager

from .config import get_settings


# SQL Command for creating the messages table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    from_msisdn TEXT NOT NULL,
    to_msisdn TEXT NOT NULL,
    ts TEXT NOT NULL,
    text TEXT,
    created_at TEXT NOT NULL
);
"""

# Creating index for common query patterns
CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts);
CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_msisdn);
"""


class DatabaseError(Exception):
    """Custom database error."""
    pass


class Storage:
    """SQLite storage operations."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_settings().db_path
        self._initialized = False
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with proper error handling."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def init_db(self) -> None:
        """Initialize the database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_TABLE_SQL)
            cursor.executescript(CREATE_INDEXES_SQL)
        self._initialized = True
    
    def is_ready(self) -> bool:
        """Check if database is reachable and initialized."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM messages LIMIT 1")
            return True
        except Exception:
            return False
    
    def insert_message(
        self,
        message_id: str,
        from_msisdn: str,
        to_msisdn: str,
        ts: str,
        text: Optional[str]
    ) -> tuple[bool, bool]:
        """
        Insert a message into the database.
        
        Returns:
            tuple[bool, bool]: (success, is_duplicate)
            - (True, False): New message inserted
            - (True, True): Message already exists (idempotent)
            - (False, False): Insert failed
        """
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (message_id, from_msisdn, to_msisdn, ts, text, created_at)
                )
                return (True, False)
            except sqlite3.IntegrityError:
                # Duplicate message_id - this is expected for idempotency
                return (True, True)
    
    def get_messages(
        self,
        limit: int = 50,
        offset: int = 0,
        from_filter: Optional[str] = None,
        since: Optional[str] = None,
        q: Optional[str] = None
    ) -> tuple[list[dict], int]:
        """
        Get messages with pagination and filters.
        
        Returns:
            tuple[list[dict], int]: (messages, total_count)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build WHERE clause
            conditions = []
            params = []
            
            if from_filter:
                conditions.append("from_msisdn = ?")
                params.append(from_filter)
            
            if since:
                conditions.append("ts >= ?")
                params.append(since)
            
            if q:
                conditions.append("text LIKE ?")
                params.append(f"%{q}%")
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            # Get total count
            count_sql = f"SELECT COUNT(*) FROM messages {where_clause}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]
            
            # Get paginated results
            query_sql = f"""
                SELECT message_id, from_msisdn, to_msisdn, ts, text
                FROM messages
                {where_clause}
                ORDER BY ts ASC, message_id ASC
                LIMIT ? OFFSET ?
            """
            cursor.execute(query_sql, params + [limit, offset])
            rows = cursor.fetchall()
            
            messages = [
                {
                    "message_id": row["message_id"],
                    "from_": row["from_msisdn"],
                    "to": row["to_msisdn"],
                    "ts": row["ts"],
                    "text": row["text"]
                }
                for row in rows
            ]
            
            return messages, total
    
    def get_stats(self) -> dict:
        """Get message statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total messages
            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            
            # Unique senders count
            cursor.execute("SELECT COUNT(DISTINCT from_msisdn) FROM messages")
            senders_count = cursor.fetchone()[0]
            
            # Top senders (up to 10)
            cursor.execute("""
                SELECT from_msisdn, COUNT(*) as count
                FROM messages
                GROUP BY from_msisdn
                ORDER BY count DESC
                LIMIT 10
            """)
            messages_per_sender = [
                {"from_": row["from_msisdn"], "count": row["count"]}
                for row in cursor.fetchall()
            ]
            
            # First and last message timestamps
            cursor.execute("SELECT MIN(ts), MAX(ts) FROM messages")
            row = cursor.fetchone()
            first_message_ts = row[0]
            last_message_ts = row[1]
            
            return {
                "total_messages": total_messages,
                "senders_count": senders_count,
                "messages_per_sender": messages_per_sender,
                "first_message_ts": first_message_ts,
                "last_message_ts": last_message_ts
            }


# Global storage instance
_storage: Optional[Storage] = None


def get_storage() -> Storage:
    """Get or create the global storage instance."""
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage


def init_storage() -> Storage:
    """Initialize storage and return instance."""
    storage = get_storage()
    storage.init_db()
    return storage