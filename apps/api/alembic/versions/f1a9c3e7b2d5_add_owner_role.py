"""add owner role and audit action values for rbac sprint

Revision ID: f1a9c3e7b2d5
Revises: c8e1a3f5d9b2
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f1a9c3e7b2d5'
down_revision: Union[str, Sequence[str], None] = 'c8e1a3f5d9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # New top-of-hierarchy role for the org's registering account.
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'OWNER'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres does not support removing enum values — no-op.
    pass
