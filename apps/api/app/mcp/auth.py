import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.api_key import APIKey
from app.security.hashing import hash_password, verify_password

# Keys are prefixed so they're identifiable in logs / config files.
_KEY_PREFIX = "atlas_"
_PREFIX_LOOKUP_LEN = 8  # chars after "atlas_" used as DB index


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns (raw_key, key_prefix, hashed_key).
    The raw key is shown once; only the hash is stored.
    """
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{_KEY_PREFIX}{random_part}"
    key_prefix = raw_key[:_PREFIX_LOOKUP_LEN]
    hashed = hash_password(raw_key)
    return raw_key, key_prefix, hashed


def create_api_key(
    db: Session,
    organization_id: int,
    name: str,
    expires_at: datetime | None = None,
) -> tuple[APIKey, str]:
    """
    Persist a new API key. Returns (APIKey row, raw_key).
    The caller must surface raw_key to the user immediately — it cannot
    be recovered later.
    """
    raw_key, key_prefix, hashed_key = generate_api_key()

    api_key = APIKey(
        organization_id=organization_id,
        name=name,
        key_prefix=key_prefix,
        hashed_key=hashed_key,
        expires_at=expires_at,
        is_active=True,
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return api_key, raw_key


def resolve_api_key(db: Session, raw_key: str) -> APIKey | None:
    """
    Validate a raw API key against the database.
    Returns the APIKey row if valid; None otherwise.
    Uses prefix lookup to narrow candidates before doing bcrypt comparison.
    """
    if len(raw_key) < _PREFIX_LOOKUP_LEN:
        return None

    prefix = raw_key[:_PREFIX_LOOKUP_LEN]

    candidates = (
        db.query(APIKey)
        .filter(
            APIKey.key_prefix == prefix,
            APIKey.is_active.is_(True),
        )
        .all()
    )

    for candidate in candidates:
        if candidate.expires_at and candidate.expires_at < datetime.utcnow():
            continue
        if verify_password(raw_key, candidate.hashed_key):
            # Update last_used_at without a full round-trip
            candidate.last_used_at = datetime.utcnow()
            db.commit()
            return candidate

    return None
