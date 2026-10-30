from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from app.config import TOKEN_EXPIRATION_HOURS
from app.database import Database, User

security = HTTPBearer(auto_error=False)
db = Database()


class UserRegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int


def hash_password(password: str) -> str:
    """Hash password using memory-hard scrypt key derivation with random 16-byte salt."""
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash using constant-time comparison."""
    try:
        parts = stored_hash.split("$")
        if parts[0] == "scrypt":
            n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
            salt = bytes.fromhex(parts[4])
            expected_key = bytes.fromhex(parts[5])
            computed_key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
            return secrets.compare_digest(computed_key, expected_key)
        elif stored_hash.startswith(("$2b$", "$2a$")):
            import bcrypt
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        return False
    except Exception:
        return False


def create_user_session(database: Database, user_id: int, duration_hours: int = TOKEN_EXPIRATION_HOURS) -> str:
    """Generate a cryptographically secure 256-bit bearer token and store session."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat()
    database.create_session(token=token, user_id=user_id, expires_at=expires_at)
    return token


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> User:
    """FastAPI dependency: authenticates bearer token, validates expiration and revocation, and returns user."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    session = db.get_session(token)

    if not session or session.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token expiration
    try:
        expires_at = datetime.fromisoformat(session.expires_at)
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed session expiration timestamp.",
        )

    user = db.get_user_by_id(session.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists.",
        )

    return user
