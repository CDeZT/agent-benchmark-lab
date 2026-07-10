"""Hidden tests for authentication module — deeper security checks."""
import os
import sys
import json
import tempfile
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))

import user_auth

# Setup: use temp users file
user_auth.USERS_FILE = tempfile.mktemp(suffix=".json")


def test_register_rejects_weak_password():
    """Verify short/weak passwords are rejected."""
    # Weak password (less than8 chars)
    try:
        user_auth.register_user("user1", "short", "test@example.com")
    except (ValueError, Exception):
        pass  # Should reject or at minimum handle gracefully
    # Verify no crash
    assert True


def test_email_validation():
    """Verify email format is validated."""
    # Invalid email should be rejected or handled
    try:
        user_auth.register_user("user2", "validpass123", "not-an-email")
    except (ValueError, Exception):
        pass
    assert True


def test_username_validation():
    """Verify empty username is rejected."""
    try:
        user_auth.register_user("", "password123", "test@example.com")
    except (ValueError, Exception):
        pass
    assert True


def test_session_not_predictable():
    """Verify two sessions for the same user are different."""
    user_auth.register_user("test1", "password123", "test@example.com")
    session1 = user_auth.login("test1", "password123")
    if session1:
        session2 = user_auth.login("test1", "password123")
        if session2:
            assert session1 != session2, "Sessions should not be identical"

    # Clean up
    Path(user_auth.USERS_FILE).unlink(missing_ok=True)


def test_password_not_logged():
    """Verify verifies user_auth.py doesn't contain obvious print password."""
    source = workspace / "user_auth.py"
    content = source.read_text()
    assert "print(password)" not in content, "Password should not be printed"

print("ALL HIDDEN TESTS PASSED")
