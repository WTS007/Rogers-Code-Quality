"""
Tests — Authentication Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifies token lifecycle, password hashing, and permission checks.

NOTE: test_permission_check_superadmin is an INTENTIONAL failure
used to demonstrate the AI remediation pipeline. The test asserts
that an 'admin' role token has 'superadmin' access, which is false.
"""

import time
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.auth import (
    generate_token,
    validate_token,
    check_permissions,
    hash_password,
    verify_password,
)


class TestAuthentication(unittest.TestCase):
    """Test suite for the authentication module."""

    def test_generate_token_returns_string(self):
        """generate_token should return a non-empty string."""
        token = generate_token(user_id=1, role="user")
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)

    def test_validate_token_returns_payload(self):
        """A freshly generated token should validate and contain user_id."""
        token = generate_token(user_id=42, role="admin")
        payload = validate_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["user_id"], 42)
        self.assertEqual(payload["role"], "admin")

    def test_expired_token_returns_none(self):
        """An expired token should return None on validation."""
        # Generate token that expires in 1 second
        token = generate_token(user_id=1, role="user", expiry_seconds=1)
        time.sleep(1.5)
        payload = validate_token(token)
        self.assertIsNone(payload)

    def test_hash_password_produces_hash(self):
        """Hashed password should differ from plaintext."""
        plaintext = "my_secure_password"
        hashed = hash_password(plaintext)
        self.assertNotEqual(plaintext, hashed)
        self.assertEqual(len(hashed), 64)  # SHA-256 hex digest length

    def test_verify_password_correct(self):
        """verify_password should return True for matching password."""
        password = "test_password_123"
        hashed = hash_password(password)
        self.assertTrue(verify_password(password, hashed))

    def test_verify_password_incorrect(self):
        """verify_password should return False for wrong password."""
        hashed = hash_password("correct_password")
        self.assertFalse(verify_password("wrong_password", hashed))

    def test_permission_check_valid_role(self):
        """An admin token should have 'editor' access."""
        token = generate_token(user_id=1, role="admin")
        self.assertTrue(check_permissions(token, "editor"))

    def test_permission_check_superadmin(self):
        """An admin token should have 'superadmin' access.

        *** INTENTIONAL FAILURE ***
        This test incorrectly asserts that role='admin' satisfies
        required_role='superadmin'. In the role hierarchy, admin (3)
        is below superadmin (4), so this WILL fail.

        This failure triggers the AI remediation pipeline to:
        1. Capture the pytest stderr in error_log.txt
        2. Generate a fix (either correct the assertion or elevate the role)
        3. Open an automated PR with the patch
        """
        token = generate_token(user_id=1, role="admin")
        # This assertion is wrong: admin < superadmin in the hierarchy
        self.assertTrue(check_permissions(token, "superadmin"))


if __name__ == "__main__":
    unittest.main()
