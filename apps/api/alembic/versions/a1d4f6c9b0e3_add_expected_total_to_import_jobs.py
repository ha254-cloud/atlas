"""add expected_total to import_jobs

Revision ID: a1d4f6c9b0e3
Revises: f3c5a8d7e2b1
Create Date: 2026-07-21 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1d4f6c9b0e3'
down_revision: Union[str, Sequence[str], None] = 'f3c5a8d7e2b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'import_jobs',
        sa.Column('expected_total', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('import_jobs', 'expected_total')
