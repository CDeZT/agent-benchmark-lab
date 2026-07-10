"""Authentication module with deterministic local security controls."""

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time


SECRET_KEY = os.environ.get("USER_AUTH_SECRET_KEY", "development-secret-only")
USERS_FILE = "users.json"
_SESSIONS: dict[str, tuple[str, float]] = {}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return base64.b64encode(salt + digest).decode()


def _verify_password(password: str, encoded: str) -> bool:
    try:
        raw = base64.b64decode(encoded.encode())
        salt, expected = raw[:16], raw[16:]
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return hmac.compare_digest(actual, expected)


def register_user(username: str, password: str, email: str) -> bool:
    if not username or len(password) < 8 or "@" not in email:
        return False
    users = load_users()
    if username in users:
        return False
    users[username] = {"password": hash_password(password), "email": email, "created_at": time.time()}
    save_users(users)
    return True


def login(username: str, password: str) -> str | None:
    user = load_users().get(username)
    return create_session(username) if user and _verify_password(password, user["password"]) else None


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = (username, time.time() + 3600)
    return token


def verify_session(token: str) -> str | None:
    session = _SESSIONS.get(token)
    if not session or session[1] < time.time():
        return None
    return session[0]


def load_users() -> dict:
    path = Path(USERS_FILE)
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except json.JSONDecodeError:
        return {}


def save_users(users: dict) -> None:
    Path(USERS_FILE).write_text(json.dumps(users, indent=2))


def change_password(username: str, old_password: str, new_password: str) -> bool:
    users = load_users()
    if username not in users or len(new_password) < 8 or not _verify_password(old_password, users[username]["password"]):
        return False
    users[username]["password"] = hash_password(new_password)
    save_users(users)
    return True


def delete_user(username: str, password: str) -> bool:
    users = load_users()
    if username not in users or not _verify_password(password, users[username]["password"]):
        return False
    del users[username]
    save_users(users)
    return True
