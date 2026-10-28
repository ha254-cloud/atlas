"""Add direct organizations.id foreign key to departments and branch_memberships.

Revision ID: a1c7e4b9d2f3
Revises: d5a8c1f3e7b9
Create Date: 2026-08-21

Departments and branch memberships previously scoped organization_id only
through composite foreign keys to branches (and users), with no direct
foreign key to organizations.id. Every other directly tenant-owned table
(claims, branches, users, ...) carries a direct organization_id ->
organizations.id foreign key in addition to any composite keys used for
cross-entity tenant-consistency checks. This migration closes that gap so
departments and branch_memberships follow the same explicit tenant-scoping
convention.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1c7e4b9d2f3"
down_revision: str | Sequence[str] | None = "d5a8c1f3e7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_departments_organization_id",
        "departments",
        "organizations",
        ["organization_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_branch_memberships_organization_id",
        "branch_memberships",
        "organizations",
        ["organization_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_branch_memberships_organization_id", "branch_memberships", type_="foreignkey")
    op.drop_constraint("fk_departments_organization_id", "departments", type_="foreignkey")
