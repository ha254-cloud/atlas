"""add duration_ms to import_jobs

Revision ID: f3c5a8d7e2b1
Revises: e8b2c6a4f105
Create Date: 2026-07-21 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c5a8d7e2b1'
down_revision: Union[str, Sequence[str], None] = 'e8b2c6a4f105'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'import_jobs',
        sa.Column('duration_ms', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('import_jobs', 'duration_ms')
