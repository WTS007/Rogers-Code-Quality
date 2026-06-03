"""
Tests — Database Module
~~~~~~~~~~~~~~~~~~~~~~~~
Verifies schema initialization, user CRUD, and audit logging.
Uses an in-memory SQLite database for isolation.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database import init_db, create_user, get_user, log_audit_event, get_recent_activity
from src.auth import hash_password


DB_PATH = ":memory:"


class TestDatabase(unittest.TestCase):
    """Test suite for the database module."""

    def setUp(self):
        """Initialize a fresh in-memory database before each test."""
        init_db(DB_PATH)

    def test_init_db_creates_tables(self):
        """init_db should create 'users' and 'audit_log' tables."""
        import sqlite3

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        self.assertIn("users", tables)
        self.assertIn("audit_log", tables)

    def test_create_and_get_user(self):
        """create_user should insert a user retrievable by get_user."""
        user_id = create_user(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("password123"),
            db_path=DB_PATH,
        )
        self.assertIsInstance(user_id, int)
        self.assertGreater(user_id, 0)

        user = get_user("testuser", DB_PATH)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "testuser")
        self.assertEqual(user["email"], "test@example.com")

    def test_get_nonexistent_user(self):
        """get_user should return None for unknown usernames."""
        user = get_user("nobody", DB_PATH)
        self.assertIsNone(user)

    def test_audit_log_records_events(self):
        """log_audit_event should store entries retrievable by get_recent_activity."""
        user_id = create_user(
            username="auditor",
            email="auditor@example.com",
            password_hash=hash_password("pass"),
            db_path=DB_PATH,
        )

        log_audit_event(user_id, "login", "Logged in from dashboard", db_path=DB_PATH)
        log_audit_event(user_id, "update_role", "Changed role to admin", db_path=DB_PATH)

        events = get_recent_activity(limit=10, db_path=DB_PATH)
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0]["action"], "update_role")  # Most recent first


if __name__ == "__main__":
    unittest.main()
