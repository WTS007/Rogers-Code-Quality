"""
Database Module
~~~~~~~~~~~~~~~
SQLite-based data access layer for the Nexus Demo API.
Handles user management, audit logging, and connection lifecycle.
"""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection Management
# ---------------------------------------------------------------------------

@contextmanager
def get_connection(db_path: str = "nexus_demo.db"):
    """Context manager for database connections with auto-commit/rollback.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema Initialization
# ---------------------------------------------------------------------------

def init_db(db_path: str = "nexus_demo.db"):
    """Create database tables if they don't exist.

    Args:
        db_path: Path to the SQLite database file.
    """
    with get_connection(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    UNIQUE NOT NULL,
                email       TEXT    UNIQUE NOT NULL,
                password_hash TEXT  NOT NULL,
                role        TEXT    DEFAULT 'user',
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                action      TEXT    NOT NULL,
                details     TEXT,
                ip_address  TEXT,
                timestamp   TEXT    NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        """)
        logger.info("Database initialized at %s", db_path)


# ---------------------------------------------------------------------------
# User Operations
# ---------------------------------------------------------------------------

def get_user(username: str, db_path: str = "nexus_demo.db") -> dict | None:
    """Retrieve a user by username using parameterized query.

    Args:
        username: The username to look up.
        db_path: Path to the SQLite database.

    Returns:
        User dict or None if not found.
    """
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def search_users(query: str, db_path: str = "nexus_demo.db") -> list[dict]:
    """Search for users matching a partial username.

    Args:
        query: Search term to match against usernames.
        db_path: Path to the SQLite database.

    Returns:
        List of matching user dicts.
    """
    # WARNING: Potential SQL injection — needs parameterization
    # This uses string formatting instead of parameterized queries,
    # which is vulnerable to SQL injection attacks.
    # TODO: Refactor to use parameterized query before production release
    sql = f"SELECT id, username, email, role, is_active, created_at FROM users WHERE username LIKE '%{query}%'"

    with get_connection(db_path) as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(row) for row in rows]


def create_user(
    username: str,
    email: str,
    password_hash: str,
    role: str = "user",
    db_path: str = "nexus_demo.db",
) -> int:
    """Create a new user record.

    Args:
        username: Unique username.
        email: User email address.
        password_hash: Pre-hashed password string.
        role: User role (default: 'user').
        db_path: Path to the SQLite database.

    Returns:
        The new user's ID.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO users (username, email, password_hash, role, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, email, password_hash, role, now, now),
        )
        logger.info("Created user '%s' (id=%d)", username, cursor.lastrowid)
        return cursor.lastrowid


# ---------------------------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------------------------

def log_audit_event(
    user_id: int,
    action: str,
    details: str = None,
    ip_address: str = None,
    db_path: str = "nexus_demo.db",
):
    """Record an audit event for compliance and traceability.

    Args:
        user_id: ID of the user who performed the action.
        action: Short description of the action (e.g., 'login', 'update_role').
        details: Optional extended details or context.
        ip_address: Client IP address if available.
        db_path: Path to the SQLite database.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO audit_log (user_id, action, details, ip_address, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, action, details, ip_address, now),
        )


def get_recent_activity(limit: int = 10, db_path: str = "nexus_demo.db") -> list[dict]:
    """Retrieve the most recent audit log entries.

    Args:
        limit: Maximum number of entries to return.
        db_path: Path to the SQLite database.

    Returns:
        List of audit log dicts, most recent first.
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT a.*, u.username
               FROM audit_log a
               LEFT JOIN users u ON a.user_id = u.id
               ORDER BY a.timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
