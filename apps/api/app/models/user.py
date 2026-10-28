from enum import Enum

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class UserRole(str, Enum):
    ADMIN = "admin"
    BILLER = "biller"
    AUDITOR = "auditor"
    VIEWER = "viewer"
    # Canonical Atlas roles (added alongside the legacy ones above for
    # backward compatibility with existing seeded/tested users).
    MANAGER = "manager"
    REVENUE_ANALYST = "revenue_analyst"
    APPEALS_SPECIALIST = "appeals_specialist"
    # Org owner — the account that registered the organization. Distinct
    # from ADMIN organizationally (billing/ownership transfer semantics),
    # but currently granted the same full permission set as ADMIN.
    OWNER = "owner"


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("id", "organization_id", name="uq_users_id_org"),)

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole),
        nullable=False,
        default=UserRole.VIEWER,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    organization = relationship(
        "Organization",
        back_populates="users",
    )
    branch_memberships = relationship(
        "BranchMembership",
        back_populates="user",
        cascade="all, delete-orphan",
        overlaps="branch,memberships",
    )
