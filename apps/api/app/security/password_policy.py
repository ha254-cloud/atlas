"""Password strength policy enforced at registration, invite-acceptance, and
password-reset time. Deliberately simple (length + character-class variety)
rather than importing a heavyweight zxcvbn-style dependency."""

import re

MIN_LENGTH = 10


def validate_password_strength(password: str) -> None:
    """Raises ValueError with a user-facing message if the password is too weak."""
    if len(password) < MIN_LENGTH:
        raise ValueError(f"Password must be at least {MIN_LENGTH} characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one special character")
