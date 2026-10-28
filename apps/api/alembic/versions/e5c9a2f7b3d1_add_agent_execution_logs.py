"""add agent_execution_logs table and claim_analyses.multi_agent_result

Revision ID: e5c9a2f7b3d1
Revises: d4b7f2a8c1e3
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5c9a2f7b3d1'
down_revision: Union[str, Sequence[str], None] = 'd4b7f2a8c1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'agent_execution_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('claim_id', sa.Integer(), nullable=True),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('agent_name', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_execution_logs_organization_id'), 'agent_execution_logs', ['organization_id'])
    op.create_index(op.f('ix_agent_execution_logs_claim_id'), 'agent_execution_logs', ['claim_id'])
    op.create_index(op.f('ix_agent_execution_logs_run_id'), 'agent_execution_logs', ['run_id'])
    op.create_index(op.f('ix_agent_execution_logs_agent_name'), 'agent_execution_logs', ['agent_name'])

    op.add_column('claim_analyses', sa.Column('multi_agent_result', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('claim_analyses', 'multi_agent_result')

    op.drop_index(op.f('ix_agent_execution_logs_agent_name'), table_name='agent_execution_logs')
    op.drop_index(op.f('ix_agent_execution_logs_run_id'), table_name='agent_execution_logs')
    op.drop_index(op.f('ix_agent_execution_logs_claim_id'), table_name='agent_execution_logs')
    op.drop_index(op.f('ix_agent_execution_logs_organization_id'), table_name='agent_execution_logs')
    op.drop_table('agent_execution_logs')
