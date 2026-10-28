import re

from sqlalchemy.orm import Session

from app.models.organization import Organization


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def unique_organization_slug(db: Session, name: str) -> str:
    """Generate a URL-safe slug from the organization name, appending a
    numeric suffix if it collides with an existing organization."""
    base = slugify(name) or "organization"
    slug = base
    suffix = 2
    while db.query(Organization).filter(Organization.slug == slug).first() is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
