"""add duplicate_records to import_jobs

Revision ID: d7a1e3f9c2b6
Revises: c4d8f2a91b3e
Create Date: 2026-07-21 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a1e3f9c2b6'
down_revision: Union[str, Sequence[str], None] = 'c4d8f2a91b3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'import_jobs',
        sa.Column('duplicate_records', sa.Integer(), nullable=False, server_default='0'),
    )
    op.alter_column('import_jobs', 'duplicate_records', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('import_jobs', 'duplicate_records')
