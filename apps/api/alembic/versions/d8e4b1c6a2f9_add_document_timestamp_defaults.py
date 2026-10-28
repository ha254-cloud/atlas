"""Add missing document timestamp server defaults.

Revision ID: d8e4b1c6a2f9
Revises: c7a1f4d9e2b6
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8e4b1c6a2f9"
down_revision: str | None = "c7a1f4d9e2b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("documents", "created_at", server_default=sa.text("now()"))
    op.alter_column("documents", "updated_at", server_default=sa.text("now()"))


def downgrade() -> None:
    op.alter_column("documents", "updated_at", server_default=None)
    op.alter_column("documents", "created_at", server_default=None)