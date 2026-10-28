"""Add branch ownership and claim currency snapshots.

Revision ID: d5a8c1f3e7b9
Revises: c4f9a2e7b1d6
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5a8c1f3e7b9"
down_revision: str | Sequence[str] | None = "c4f9a2e7b1d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_users_id_org", "users", ["id", "organization_id"])
    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("organization_id", "code", name="uq_branches_org_code"),
        sa.UniqueConstraint("id", "organization_id", name="uq_branches_id_org"),
    )
    op.create_index("ix_branches_organization_id", "branches", ["organization_id"])
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "organization_id"],
            ["branches.id", "branches.organization_id"],
            name="fk_departments_branch_org",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id", "branch_id", "code", name="uq_departments_branch_code"
        ),
        sa.UniqueConstraint(
            "id", "branch_id", "organization_id", name="uq_departments_id_branch_org"
        ),
    )
    op.create_index("ix_departments_organization_id", "departments", ["organization_id"])
    op.create_index("ix_departments_branch_id", "departments", ["branch_id"])
    op.create_table(
        "branch_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_template", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "organization_id"],
            ["branches.id", "branches.organization_id"],
            name="fk_branch_memberships_branch_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_branch_memberships_user_org",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id", "branch_id", "user_id", name="uq_branch_memberships"
        ),
    )
    op.create_index(
        "ix_branch_memberships_organization_id", "branch_memberships", ["organization_id"]
    )
    op.create_index("ix_branch_memberships_branch_id", "branch_memberships", ["branch_id"])
    op.create_index("ix_branch_memberships_user_id", "branch_memberships", ["user_id"])

    op.add_column("claims", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.add_column("claims", sa.Column("department_id", sa.Integer(), nullable=True))
    op.add_column("claims", sa.Column("currency", sa.String(length=3), nullable=True))
    op.execute(
        "UPDATE claims SET currency = organizations.currency "
        "FROM organizations WHERE claims.organization_id = organizations.id"
    )
    op.alter_column("claims", "currency", nullable=False)
    op.create_index("ix_claims_branch_id", "claims", ["branch_id"])
    op.create_index("ix_claims_department_id", "claims", ["department_id"])
    op.create_foreign_key(
        "fk_claims_branch_org",
        "claims",
        "branches",
        ["branch_id", "organization_id"],
        ["id", "organization_id"],
    )
    op.create_foreign_key(
        "fk_claims_department_branch_org",
        "claims",
        "departments",
        ["department_id", "branch_id", "organization_id"],
        ["id", "branch_id", "organization_id"],
    )
    op.create_check_constraint(
        "ck_claims_department_requires_branch",
        "claims",
        "department_id IS NULL OR branch_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_claims_department_requires_branch", "claims", type_="check")
    op.drop_constraint("fk_claims_department_branch_org", "claims", type_="foreignkey")
    op.drop_constraint("fk_claims_branch_org", "claims", type_="foreignkey")
    op.drop_index("ix_claims_department_id", table_name="claims")
    op.drop_index("ix_claims_branch_id", table_name="claims")
    op.drop_column("claims", "currency")
    op.drop_column("claims", "department_id")
    op.drop_column("claims", "branch_id")
    op.drop_table("branch_memberships")
    op.drop_table("departments")
    op.drop_table("branches")
    op.drop_constraint("uq_users_id_org", "users", type_="unique")