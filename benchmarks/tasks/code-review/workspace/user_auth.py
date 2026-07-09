"""User authentication module.

This module handles user registration, login, and session management.
It has several security issues that need to be fixed.
"""

import hashlib
import json
import os
import time
from pathlib import Path


# BUG: Hardcoded secret key
SECRET_KEY = "my-secret-key-123"

# BUG: Storing passwords in plain text
USERS_FILE = "users.json"


def hash_password(password):
    """Hash a password using SHA-256.

    BUG: Using SHA-256 without salt is insecure.
    Should use bcrypt or argon2 with proper salt.
    """
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password, email):
    """Register a new user.

    BUG: No input validation.
    BUG: No duplicate username check.
    """
    users = load_users()

    # BUG: Storing password in plain text
    users[username] = {
        "password": password,  # Should be hashed
        "email": email,
        "created_at": time.time(),
    }

    save_users(users)
    return True


def login(username, password):
    """Authenticate a user.

    BUG: No rate limiting.
    BUG: Timing attack vulnerable.
    """
    users = load_users()

    if username not in users:
        return False

    # BUG: Comparing plain text passwords
    if users[username]["password"] == password:
        return create_session(username)

    return None


def create_session(username):
    """Create a session for a user.

    BUG: Session token is predictable.
    """
    # BUG: Using simple timestamp as token
    token = f"{username}-{int(time.time())}"
    return token


def verify_session(token):
    """Verify a session token.

    BUG: No expiration check.
    """
    # BUG: No actual verification
    return token.split("-")[0] if "-" in token else None


def load_users():
    """Load users from file."""
    path = Path(USERS_FILE)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_users(users):
    """Save users to file."""
    Path(USERS_FILE).write_text(json.dumps(users, indent=2))


def change_password(username, old_password, new_password):
    """Change user password.

    BUG: No verification of old password.
    """
    users = load_users()

    if username not in users:
        return False

    # BUG: Not verifying old password
    users[username]["password"] = new_password
    save_users(users)
    return True


def delete_user(username, password):
    """Delete a user account.

    BUG: No password verification before deletion.
    """
    users = load_users()

    if username not in users:
        return False

    # BUG: Not verifying password before deletion
    del users[username]
    save_users(users)
    return True
