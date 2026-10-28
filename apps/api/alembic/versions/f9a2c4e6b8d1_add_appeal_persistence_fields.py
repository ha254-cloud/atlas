"""Add Sprint 12.1 appeal persistence fields.

Revision ID: f9a2c4e6b8d1
Revises: a4e8c2d6f1b9
Create Date: 2026-08-01 10:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f9a2c4e6b8d1"
down_revision: Union[str, Sequence[str], None] = "a4e8c2d6f1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE appealstatus ADD VALUE IF NOT EXISTS 'GENERATED'")
    op.add_column("appeals", sa.Column("confidence", sa.Numeric(5, 4), nullable=True))
    op.add_column("appeals", sa.Column("required_documents", sa.JSON(), nullable=True))
    op.add_column("appeals", sa.Column("references", sa.JSON(), nullable=True))
    op.add_column("appeals", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.add_column(
        "appeals",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_appeals_approved_by_users",
        "appeals",
        "users",
        ["approved_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_appeals_approved_by_users",
        "appeals",
        type_="foreignkey",
    )
    op.drop_column("appeals", "approved_at")
    op.drop_column("appeals", "approved_by")
    op.drop_column("appeals", "references")
    op.drop_column("appeals", "required_documents")
    op.drop_column("appeals", "confidence")
    # PostgreSQL enum values are intentionally retained on downgrade.
