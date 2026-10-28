from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base
from app.models.user import UserRole


class Invitation(Base, TimestampMixin):
    """An invite for someone to join an existing organization with a given
    role. The invited person never creates a new organization — accepting
    the invite simply creates their User row under the inviter's org."""

    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole),
        nullable=False,
        default=UserRole.VIEWER,
    )

    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)

    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
