from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base


class APIKey(Base, TimestampMixin):
    """
    API keys allow MCP clients (AI agents, integrations) to authenticate
    without a user session.  Keys are scoped to an organization so every
    tool call automatically inherits the correct tenant context.

    The raw key is shown to the customer exactly once at creation time.
    Only the bcrypt hash is persisted — never the plaintext value.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # First 8 chars of the raw key — used to look up the correct row
    # before doing the full bcrypt comparison.
    key_prefix: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
    )

    hashed_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
