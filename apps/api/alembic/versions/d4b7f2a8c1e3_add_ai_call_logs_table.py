"""add ai_call_logs table for AI Gateway cost/usage tracking

Revision ID: d4b7f2a8c1e3
Revises: c2f8a4e1d9b6
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b7f2a8c1e3'
down_revision: Union[str, Sequence[str], None] = 'c2f8a4e1d9b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ai_call_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('claim_id', sa.Integer(), nullable=True),
        sa.Column('task', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=20), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('cache_hit', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_call_logs_organization_id'), 'ai_call_logs', ['organization_id'])
    op.create_index(op.f('ix_ai_call_logs_claim_id'), 'ai_call_logs', ['claim_id'])
    op.create_index(op.f('ix_ai_call_logs_task'), 'ai_call_logs', ['task'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_ai_call_logs_task'), table_name='ai_call_logs')
    op.drop_index(op.f('ix_ai_call_logs_claim_id'), table_name='ai_call_logs')
    op.drop_index(op.f('ix_ai_call_logs_organization_id'), table_name='ai_call_logs')
    op.drop_table('ai_call_logs')
