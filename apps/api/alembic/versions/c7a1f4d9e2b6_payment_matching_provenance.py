"""Add payment matching provenance.

Revision ID: c7a1f4d9e2b6
Revises: b5d9e2f7c1a4
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7a1f4d9e2b6"
down_revision: str | None = "b5d9e2f7c1a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("matched_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("matching_method", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("matching_reason", sa.String(length=500), nullable=True),
    )
    op.create_foreign_key(
        "fk_payments_matched_by_id_users",
        "payments",
        "users",
        ["matched_by_id"],
        ["id"],
    )
    op.create_index(
        "ix_payments_matched_by_id",
        "payments",
        ["matched_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_payments_org_unmatched",
        "payments",
        ["organization_id", "payment_date"],
        unique=False,
        postgresql_where=sa.text("claim_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_payments_org_unmatched", table_name="payments")
    op.drop_index("ix_payments_matched_by_id", table_name="payments")
    op.drop_constraint(
        "fk_payments_matched_by_id_users",
        "payments",
        type_="foreignkey",
    )
    op.drop_column("payments", "matching_reason")
    op.drop_column("payments", "matching_method")
    op.drop_column("payments", "matched_by_id")
