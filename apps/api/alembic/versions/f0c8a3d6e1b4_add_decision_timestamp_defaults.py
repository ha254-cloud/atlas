"""Add missing Decision Intelligence timestamp defaults.

Revision ID: f0c8a3d6e1b4
Revises: e1a7c4d9b2f6
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f0c8a3d6e1b4"
down_revision: str | Sequence[str] | None = "e1a7c4d9b2f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in ("claim_decisions", "payer_statistics"):
        op.alter_column(table_name, "created_at", server_default=sa.text("now()"))
        op.alter_column(table_name, "updated_at", server_default=sa.text("now()"))


def downgrade() -> None:
    for table_name in ("payer_statistics", "claim_decisions"):
        op.alter_column(table_name, "updated_at", server_default=None)
        op.alter_column(table_name, "created_at", server_default=None)
