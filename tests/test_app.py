"""
Tests — Application Endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifies core Flask routes return expected status codes and data shapes.
"""

import json
import unittest
import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.app import create_app


class TestAppEndpoints(unittest.TestCase):
    """Test suite for the Nexus Demo API application routes."""

    def setUp(self):
        """Create a test client with a clean temporary database."""
        os.environ["APP_ENV"] = "testing"
        if os.path.exists("nexus_test.db"):
            try:
                os.remove("nexus_test.db")
            except OSError:
                pass
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up database file after test execution."""
        if os.path.exists("nexus_test.db"):
            try:
                os.remove("nexus_test.db")
            except OSError:
                pass

    def test_health_endpoint(self):
        """GET /api/health should return 200 with status field."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("status", data)
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "nexus-demo-api")

    def test_index_page(self):
        """GET / should return 200 (static HTML page)."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_404_handler(self):
        """GET /nonexistent should return 404 JSON error."""
        response = self.client.get("/this-route-does-not-exist")
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn("error", data)

    def test_users_endpoint(self):
        """GET /api/users should return 200 with a users list."""
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("users", data)
        self.assertIsInstance(data["users"], list)

    def test_register_user(self):
        """POST /api/users should create a new user."""
        response = self.client.post(
            "/api/users",
            data=json.dumps({
                "username": "testuser",
                "email": "test@example.com",
                "password": "securepassword123",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data["username"], "testuser")

    def test_register_duplicate_user(self):
        """POST /api/users with existing username should return 409."""
        # 'admin' is seeded by default
        response = self.client.post(
            "/api/users",
            data=json.dumps({
                "username": "admin",
                "email": "admin2@example.com",
                "password": "password",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
