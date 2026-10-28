"""Secure random token generation for email verification, password reset,
and invitation links."""

import secrets
from datetime import UTC, datetime


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def is_expired(expires_at: datetime) -> bool:
    """True if expires_at is in the past. Tolerates naive datetimes (e.g.
    from SQLite in tests, which doesn't preserve tzinfo) by assuming UTC."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at < datetime.now(UTC)
