"""add claim_workflows table for the recovery workflow engine

Revision ID: a7e2c9f4d1b6
Revises: f1a9c3e7b2d5
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7e2c9f4d1b6'
down_revision: Union[str, Sequence[str], None] = 'f1a9c3e7b2d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


claim_workflow_state_enum = sa.Enum(
    'IMPORTED', 'VALIDATED', 'ANALYZED', 'WAITING_FOR_DOCUMENTS',
    'READY_FOR_APPEAL', 'APPEAL_GENERATED', 'UNDER_REVIEW', 'APPROVED',
    'SUBMITTED', 'PENDING_PAYER', 'RECOVERED', 'CLOSED',
    name='claimworkflowstate',
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'claim_workflows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('state', claim_workflow_state_enum, nullable=False),
        sa.Column('previous_state', claim_workflow_state_enum, nullable=True),
        sa.Column('state_entered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('priority_score', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('escalated', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('claim_id'),
    )
    op.create_index(op.f('ix_claim_workflows_organization_id'), 'claim_workflows', ['organization_id'], unique=False)
    op.create_index(op.f('ix_claim_workflows_claim_id'), 'claim_workflows', ['claim_id'], unique=False)
    op.create_index(op.f('ix_claim_workflows_state'), 'claim_workflows', ['state'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_claim_workflows_state'), table_name='claim_workflows')
    op.drop_index(op.f('ix_claim_workflows_claim_id'), table_name='claim_workflows')
    op.drop_index(op.f('ix_claim_workflows_organization_id'), table_name='claim_workflows')
    op.drop_table('claim_workflows')
    claim_workflow_state_enum.drop(op.get_bind(), checkfirst=True)
