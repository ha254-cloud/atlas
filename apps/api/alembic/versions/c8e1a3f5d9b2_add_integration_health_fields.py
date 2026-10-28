"""add last_error and claims_imported_count to integrations

Revision ID: c8e1a3f5d9b2
Revises: b6d3e9f1a4c7
Create Date: 2026-07-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8e1a3f5d9b2'
down_revision = 'b6d3e9f1a4c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('integrations', sa.Column('last_error', sa.Text(), nullable=True))
    op.add_column(
        'integrations',
        sa.Column('claims_imported_count', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('integrations', 'claims_imported_count')
    op.drop_column('integrations', 'last_error')
