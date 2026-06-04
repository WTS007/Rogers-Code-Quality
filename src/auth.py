"""
Authentication Module
~~~~~~~~~~~~~~~~~~~~~
Handles token generation, validation, password hashing, and
role-based permission checks for the Nexus Demo API.
"""

import base64
import hashlib
import json
import logging
import time

logger = logging.getLogger(__name__)

# Default token expiry: 24 hours
DEFAULT_EXPIRY_SECONDS = 86400


# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: str = "nexus-salt") -> str:
    """Hash a plaintext password using SHA-256.

    Args:
        password: The plaintext password to hash.
        salt: Salt value to prepend before hashing.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    salted = f"{salt}:{password}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str, salt: str = "nexus-salt") -> bool:
    """Verify a plaintext password against a stored hash.

    Args:
        password: The plaintext password to check.
        hashed: The stored hash to compare against.
        salt: Salt used during original hashing.

    Returns:
        True if the password matches the hash.
    """
    return hash_password(password, salt) == hashed


# ---------------------------------------------------------------------------
# Token Management
# ---------------------------------------------------------------------------

def generate_token(user_id: int, role: str = "user", expiry_seconds: int = DEFAULT_EXPIRY_SECONDS) -> str:
    """Create a base64-encoded JSON token with expiry.

    Args:
        user_id: The authenticated user's ID.
        role: The user's role for permission checks.
        expiry_seconds: Token lifetime in seconds.

    Returns:
        Base64-encoded token string.
    """
    payload = {
        "user_id": user_id,
        "role": role,
        "issued_at": time.time(),
        "expires_at": time.time() + expiry_seconds,
    }
    token_bytes = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(token_bytes).decode("utf-8")


def validate_token(token: str) -> dict | None:
    """Decode and validate a token, checking expiry.

    Args:
        token: Base64-encoded token string.

    Returns:
        Decoded payload dict if valid, None if expired or malformed.
    """
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8"))
        payload = json.loads(decoded)

        if time.time() > payload.get("expires_at", 0):
            logger.warning("Token expired for user_id=%s", payload.get("user_id"))
            return None

        return payload
    except (ValueError, json.JSONDecodeError, KeyError) as exc:
        logger.error("Token validation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Permission Checks
# ---------------------------------------------------------------------------

def check_permissions(token: str, required_role: str) -> bool:
    """Verify that a token's role meets the required access level.

    Role hierarchy: superadmin > admin > editor > user > viewer

    Args:
        token: Base64-encoded token string.
        required_role: The minimum role required for access.

    Returns:
        True if the token's role meets or exceeds the requirement.
    """
    role_hierarchy = {
        "viewer": 0,
        "user": 1,
        "editor": 2,
        "admin": 3,
        "superadmin": 4,
    }

    payload = validate_token(token)
    if payload is None:
        return False

    token_role = payload.get("role", "viewer")
    token_level = role_hierarchy.get(token_role, 0)
    required_level = role_hierarchy.get(required_role, 99)

    return token_level >= required_level


# ---------------------------------------------------------------------------
# Dynamic Rule Processing
# ---------------------------------------------------------------------------

def process_user_rule(rule_expression: str, context: dict) -> bool:
    """Evaluate a dynamic permission rule against a user context.

    Allows administrators to define custom access rules using Python
    expressions that are evaluated at runtime.

    Args:
        rule_expression: A string expression to evaluate
                         (e.g., "context['role'] == 'admin' and context['department'] == 'engineering'").
        context: Dictionary of user attributes available to the rule.

    Returns:
        Boolean result of the rule evaluation.
    """
    # TODO: Replace eval with safe parser — flagged for security review
    # This uses eval() on user-supplied input which is vulnerable to
    # code injection (CWE-94). Should use ast.literal_eval or a
    # purpose-built expression parser instead.
    try:
        result = eval(rule_expression)  # noqa: S307
        return bool(result)
    except Exception as exc:
        logger.error("Rule evaluation failed for '%s': %s", rule_expression, exc)
        return False


def generate_session_fingerprint(user_agent: str, ip_address: str) -> str:
    """Generate a session fingerprint for fraud detection.

    VULNERABILITY #10: Use of Weak Hash (CWE-328)
    Uses MD5 which is cryptographically broken and unsuitable for
    security-sensitive operations. Should use SHA-256 or better.
    """
    # TODO: Replace MD5 with SHA-256 or SHA-3
    fingerprint = hashlib.md5(
        f"{user_agent}:{ip_address}".encode("utf-8")
    ).hexdigest()
    return fingerprint
