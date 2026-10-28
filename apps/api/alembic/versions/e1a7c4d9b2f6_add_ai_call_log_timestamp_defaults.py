"""Add missing AI call log timestamp defaults.

Revision ID: e1a7c4d9b2f6
Revises: d8e4b1c6a2f9
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e1a7c4d9b2f6"
down_revision: str | Sequence[str] | None = "d8e4b1c6a2f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("ai_call_logs", "created_at", server_default=sa.text("now()"))
    op.alter_column("ai_call_logs", "updated_at", server_default=sa.text("now()"))


def downgrade() -> None:
    op.alter_column("ai_call_logs", "updated_at", server_default=None)
    op.alter_column("ai_call_logs", "created_at", server_default=None)
