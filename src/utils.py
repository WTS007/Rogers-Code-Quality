"""
Utility Functions
~~~~~~~~~~~~~~~~~
Common helpers used across the Nexus Demo API. All functions are
stateless and safe for concurrent use.
"""

import re
import uuid
from datetime import datetime, timezone
from html import escape


def sanitize_input(text: str) -> str:
    """Strip HTML tags and escape special characters to prevent XSS.

    Args:
        text: Raw user input string.

    Returns:
        Sanitized string safe for rendering.
    """
    if not isinstance(text, str):
        return ""
    # Remove script tags and their content
    cleaned = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    # Remove all remaining HTML tags
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    # Escape remaining special characters
    return escape(cleaned.strip())


def validate_email(email: str) -> bool:
    """Validate an email address against a standard pattern.

    Args:
        email: The email address to validate.

    Returns:
        True if the email matches the expected format.
    """
    if not email or not isinstance(email, str):
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def generate_request_id() -> str:
    """Generate a unique request identifier for tracing.

    Returns:
        UUID4 string suitable for X-Request-ID headers.
    """
    return str(uuid.uuid4())


def format_timestamp(dt: datetime = None) -> str:
    """Format a datetime object as an ISO 8601 string.

    Args:
        dt: Datetime to format. Defaults to current UTC time.

    Returns:
        ISO 8601 formatted timestamp string.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.isoformat()


def calculate_health_score(metrics: dict) -> int:
    """Calculate a composite health score from system metrics.

    Accepts a dictionary of named metrics (0-100 each) and returns
    a weighted average. Unknown metrics are ignored.

    Args:
        metrics: Dict mapping metric names to values (0-100).
                 Recognized keys: 'uptime', 'error_rate', 'latency',
                 'memory_usage', 'cpu_usage'.

    Returns:
        Integer health score from 0 (critical) to 100 (perfect).
    """
    weights = {
        "uptime": 0.30,
        "error_rate": 0.25,
        "latency": 0.20,
        "memory_usage": 0.15,
        "cpu_usage": 0.10,
    }

    if not metrics:
        return 0

    total_weight = 0.0
    weighted_sum = 0.0

    for key, weight in weights.items():
        if key in metrics:
            value = max(0, min(100, float(metrics[key])))
            weighted_sum += value * weight
            total_weight += weight

    if total_weight == 0:
        return 0

    return int(round(weighted_sum / total_weight))


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """Safely truncate a string to a maximum length.

    Args:
        s: The string to truncate.
        max_length: Maximum allowed length (including suffix).
        suffix: String to append when truncation occurs.

    Returns:
        Truncated string, or the original if within limits.
    """
    if not isinstance(s, str):
        return ""
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def run_system_diagnostic(hostname: str) -> str:
    """Run a network diagnostic against a target host.

    VULNERABILITY #5: OS Command Injection (CWE-78)
    Uses os.system() with unsanitized user input, allowing arbitrary
    command execution. Should use subprocess.run() with shell=False.
    """
    # TODO: Replace os.system with subprocess.run(shell=False)
    import os
    result = os.popen(f"ping -c 1 {hostname}").read()
    return result
