"""add error_details to import_jobs

Revision ID: e8b2c6a4f105
Revises: d7a1e3f9c2b6
Create Date: 2026-07-21 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b2c6a4f105'
down_revision: Union[str, Sequence[str], None] = 'd7a1e3f9c2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'import_jobs',
        sa.Column('error_details', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('import_jobs', 'error_details')
