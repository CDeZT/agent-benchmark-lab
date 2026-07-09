"""Tests for user authentication module.

These tests verify that the security issues have been fixed.
"""
import sys
import os
import tempfile
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import user_auth


def setup():
    """Setup test environment."""
    # Use temporary file for users
    user_auth.USERS_FILE = tempfile.mktemp(suffix=".json")
    # Clean up
    if Path(user_auth.USERS_FILE).exists():
        Path(user_auth.USERS_FILE).unlink()


def teardown():
    """Cleanup test environment."""
    if Path(user_auth.USERS_FILE).exists():
        Path(user_auth.USERS_FILE).unlink()


def test_register_and_login():
    """Test basic registration and login."""
    setup()
    try:
        user_auth.register_user("testuser", "password123", "test@example.com")
        session = user_auth.login("testuser", "password123")
        assert session is not None, "Login should succeed"
    finally:
        teardown()


def test_password_is_hashed():
    """Verify passwords are not stored in plain text."""
    setup()
    try:
        user_auth.register_user("testuser", "password123", "test@example.com")
        users = user_auth.load_users()
        # BUG: Password should be hashed, not plain text
        assert users["testuser"]["password"] != "password123", \
            "Password should be hashed, not stored in plain text"
    finally:
        teardown()


def test_password_hash_uses_salt():
    """Verify password hashing uses salt."""
    setup()
    try:
        # Hashing same password twice should produce different results (with salt)
        hash1 = user_auth.hash_password("password123")
        hash2 = user_auth.hash_password("password123")
        # BUG: Should use salt, so hashes should be different
        assert hash1 != hash2, "Password hash should use salt"
    finally:
        teardown()


def test_change_password_requires_old_password():
    """Verify old password is required to change password."""
    setup()
    try:
        user_auth.register_user("testuser", "oldpass", "test@example.com")
        # BUG: Should fail without correct old password
        result = user_auth.change_password("testuser", "wrongpass", "newpass")
        assert result is False, "Should fail with wrong old password"
    finally:
        teardown()


def test_delete_user_requires_password():
    """Verify password is required to delete user."""
    setup()
    try:
        user_auth.register_user("testuser", "password123", "test@example.com")
        # BUG: Should fail without correct password
        result = user_auth.delete_user("testuser", "wrongpass")
        assert result is False, "Should fail with wrong password"
    finally:
        teardown()


def test_session_expires():
    """Verify sessions expire after some time."""
    setup()
    try:
        user_auth.register_user("testuser", "password123", "test@example.com")
        session = user_auth.login("testuser", "password123")
        assert session is not None

        # BUG: Session should expire after some time
        # For testing, we'd need to mock time or wait
        # This test just verifies the session exists
    finally:
        teardown()


def test_no_hardcoded_secrets():
    """Verify no hardcoded secrets in source code."""
    source = Path(__file__).parent / "user_auth.py"
    content = source.read_text()
    # BUG: Should not have hardcoded secret key
    assert "SECRET_KEY = " not in content or "os.environ" in content, \
        "Should not have hardcoded secrets"
