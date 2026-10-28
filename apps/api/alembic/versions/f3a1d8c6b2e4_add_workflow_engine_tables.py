"""add workflow_definitions, workflow_steps, workflow_executions, workflow_step_executions

Revision ID: f3a1d8c6b2e4
Revises: e5c9a2f7b3d1
Create Date: 2026-07-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a1d8c6b2e4'
down_revision: Union[str, Sequence[str], None] = 'e5c9a2f7b3d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'workflow_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_event', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_workflow_definitions_organization_id'), 'workflow_definitions', ['organization_id']
    )
    op.create_index(
        op.f('ix_workflow_definitions_trigger_event'), 'workflow_definitions', ['trigger_event']
    )

    op.create_table(
        'workflow_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column(
            'step_type',
            sa.Enum(
                'AI_ANALYSIS', 'GENERATE_APPEAL', 'CONDITION', 'HUMAN_APPROVAL', 'WAIT', 'EMAIL',
                'NOTIFICATION', 'ASSIGN_USER', 'UPLOAD_DOCUMENT', 'CALL_API', 'LOOP', 'END',
                name='workflowsteptype',
            ),
            nullable=False,
        ),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('next_step_id', sa.Integer(), nullable=True),
        sa.Column('failure_step_id', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('retry_delay_seconds', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflow_definitions.id']),
        sa.ForeignKeyConstraint(['next_step_id'], ['workflow_steps.id']),
        sa.ForeignKeyConstraint(['failure_step_id'], ['workflow_steps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workflow_steps_workflow_id'), 'workflow_steps', ['workflow_id'])

    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'RUNNING', 'WAITING_APPROVAL', 'WAITING', 'FAILED', 'COMPLETED', 'CANCELLED',
                name='workflowexecutionstatus',
            ),
            nullable=False,
        ),
        sa.Column('current_step_id', sa.Integer(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflow_definitions.id']),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
        sa.ForeignKeyConstraint(['current_step_id'], ['workflow_steps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workflow_executions_organization_id'), 'workflow_executions', ['organization_id'])
    op.create_index(op.f('ix_workflow_executions_workflow_id'), 'workflow_executions', ['workflow_id'])
    op.create_index(op.f('ix_workflow_executions_claim_id'), 'workflow_executions', ['claim_id'])
    op.create_index(op.f('ix_workflow_executions_status'), 'workflow_executions', ['status'])

    op.create_table(
        'workflow_step_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('step_id', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('SUCCEEDED', 'FAILED', 'WAITING', 'SKIPPED', name='workflowstepexecutionstatus'),
            nullable=False,
        ),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('output', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id']),
        sa.ForeignKeyConstraint(['step_id'], ['workflow_steps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_workflow_step_executions_execution_id'), 'workflow_step_executions', ['execution_id']
    )
    op.create_index(op.f('ix_workflow_step_executions_step_id'), 'workflow_step_executions', ['step_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_workflow_step_executions_step_id'), table_name='workflow_step_executions')
    op.drop_index(op.f('ix_workflow_step_executions_execution_id'), table_name='workflow_step_executions')
    op.drop_table('workflow_step_executions')

    op.drop_index(op.f('ix_workflow_executions_status'), table_name='workflow_executions')
    op.drop_index(op.f('ix_workflow_executions_claim_id'), table_name='workflow_executions')
    op.drop_index(op.f('ix_workflow_executions_workflow_id'), table_name='workflow_executions')
    op.drop_index(op.f('ix_workflow_executions_organization_id'), table_name='workflow_executions')
    op.drop_table('workflow_executions')

    op.drop_index(op.f('ix_workflow_steps_workflow_id'), table_name='workflow_steps')
    op.drop_table('workflow_steps')

    op.drop_index(op.f('ix_workflow_definitions_trigger_event'), table_name='workflow_definitions')
    op.drop_index(op.f('ix_workflow_definitions_organization_id'), table_name='workflow_definitions')
    op.drop_table('workflow_definitions')

    sa.Enum(name='workflowstepexecutionstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='workflowexecutionstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='workflowsteptype').drop(op.get_bind(), checkfirst=True)
