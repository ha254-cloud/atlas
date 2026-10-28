"""add missing_documents to appeals

Revision ID: b6d3e9f1a4c7
Revises: a1f4d7c2b8e5
Create Date: 2026-07-24 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6d3e9f1a4c7'
down_revision: Union[str, Sequence[str], None] = 'a1f4d7c2b8e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('appeals', sa.Column('missing_documents', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('appeals', 'missing_documents')
