"""
auth.py — Zenith 2.0 Authentication
RULE: All auth checks go through functions here.
      Users stored in database with bcrypt password hashing.
"""
import functools
import logging
import bcrypt
from flask import session, redirect, url_for, request
from core.db import get_db, fetchone, execute, transaction

log = logging.getLogger("zenith.auth")


def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    if not hashed:
        log.error("verify_password: empty hash — possible DB corruption")
        return False
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception as e:
        log.error("verify_password bcrypt error: %s", e)
        return False


def is_authed() -> bool:
    return session.get("authed") is True


def get_current_user() -> str | None:
    return session.get("user")


def get_role() -> str | None:
    return session.get("role")


def is_admin() -> bool:
    return session.get("role") == "admin"


def login(username: str, password: str) -> bool:
    """Authenticate user against database. Returns True on success."""
    conn = get_db()
    user = fetchone(
        conn,
        "SELECT id, username, password_hash, role FROM users WHERE username = %s",
        [username]
    )

    if not user or not verify_password(password, user["password_hash"]):
        return False

    session["authed"] = True
    session["user"] = user["username"]
    session["role"] = user["role"]
    return True


def register(username: str, password: str, role: str = "guest") -> bool:
    """Create new user. Returns True on success, False if user exists."""
    if role not in ("admin", "guest"):
        return False

    conn = get_db()
    existing = fetchone(conn, "SELECT id FROM users WHERE username = %s", [username])
    if existing:
        return False

    password_hash = hash_password(password)

    try:
        with transaction(conn):
            execute(
                conn,
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                [username, password_hash, role]
            )
        return True
    except Exception:
        return False


def logout():
    session.clear()


def require_auth(fn):
    """Decorator: redirect unauthenticated requests to /login."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authed():
            return redirect(url_for("main.login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    """Decorator: 403 for non-admin users."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authed():
            return redirect(url_for("main.login", next=request.path))
        if not is_admin():
            from flask import abort
            abort(403)
        return fn(*args, **kwargs)
    return wrapper
