"""add claim_analyses table and extend denialtype enum

Revision ID: b3f9e1c7a4d2
Revises: e6c1a9f4b2d7
Create Date: 2026-07-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3f9e1c7a4d2'
down_revision: Union[str, Sequence[str], None] = 'e6c1a9f4b2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


analysis_status_enum = sa.Enum('PENDING', 'COMPLETED', 'FAILED', name='analysisstatus')


def upgrade() -> None:
    """Upgrade schema."""
    # Later migrations seed rows with these labels, so commit the enum change
    # before PostgreSQL permits the new values to be used.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE denialtype ADD VALUE IF NOT EXISTS 'MODIFIER_ERROR'")
        op.execute("ALTER TYPE denialtype ADD VALUE IF NOT EXISTS 'NON_COVERED_SERVICE'")
        op.execute("ALTER TYPE denialtype ADD VALUE IF NOT EXISTS 'COORDINATION_OF_BENEFITS'")

    op.create_table(
        'claim_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('analysis_status', analysis_status_enum, nullable=False),
        sa.Column('denial_category', sa.String(length=50), nullable=True),
        sa.Column('root_cause', sa.String(length=100), nullable=True),
        sa.Column('recovery_probability', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('estimated_recovery_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('recommended_action', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('claim_id'),
    )
    op.create_index(op.f('ix_claim_analyses_organization_id'), 'claim_analyses', ['organization_id'], unique=False)
    op.create_index(op.f('ix_claim_analyses_claim_id'), 'claim_analyses', ['claim_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_claim_analyses_claim_id'), table_name='claim_analyses')
    op.drop_index(op.f('ix_claim_analyses_organization_id'), table_name='claim_analyses')
    op.drop_table('claim_analyses')
    analysis_status_enum.drop(op.get_bind(), checkfirst=True)
    # Postgres cannot remove values from an existing enum type; the added
    # denialtype values are left in place on downgrade.
