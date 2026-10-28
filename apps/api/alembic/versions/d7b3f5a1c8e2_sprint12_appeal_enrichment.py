"""sprint12 appeal enrichment: title, attachments, missing_information, quality_score

Revision ID: d7b3f5a1c8e2
Revises: f1a3c7e9b2d5
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7b3f5a1c8e2'
down_revision: Union[str, Sequence[str], None] = 'f1a3c7e9b2d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('appeals', sa.Column('title', sa.String(length=255), nullable=True))
    op.add_column('appeals', sa.Column('attachments', sa.JSON(), nullable=True))
    op.add_column('appeals', sa.Column('missing_information', sa.JSON(), nullable=True))
    op.add_column('appeals', sa.Column('quality_score', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('appeals', 'quality_score')
    op.drop_column('appeals', 'missing_information')
    op.drop_column('appeals', 'attachments')
    op.drop_column('appeals', 'title')
