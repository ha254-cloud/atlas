from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_branches_org_code"),
        UniqueConstraint("id", "organization_id", name="uq_branches_id_org"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    departments = relationship("Department", back_populates="branch", cascade="all, delete-orphan")
    memberships = relationship(
        "BranchMembership",
        back_populates="branch",
        cascade="all, delete-orphan",
        overlaps="branch_memberships,user",
    )


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "organization_id"],
            ["branches.id", "branches.organization_id"],
            name="fk_departments_branch_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organization_id", "branch_id", "code", name="uq_departments_branch_code"),
        UniqueConstraint("id", "branch_id", "organization_id", name="uq_departments_id_branch_org"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    branch_id: Mapped[int] = mapped_column(index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    branch = relationship("Branch", back_populates="departments")


class BranchMembership(Base, TimestampMixin):
    __tablename__ = "branch_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "organization_id"],
            ["branches.id", "branches.organization_id"],
            name="fk_branch_memberships_branch_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_branch_memberships_user_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint("organization_id", "branch_id", "user_id", name="uq_branch_memberships"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    branch_id: Mapped[int] = mapped_column(index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(index=True, nullable=False)
    role_template: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    branch = relationship(
        "Branch", back_populates="memberships", overlaps="branch_memberships,user"
    )
    user = relationship("User", back_populates="branch_memberships", overlaps="branch,memberships")
