"""add claim_decisions and payer_statistics tables

Revision ID: a7d2c9f4b8e1
Revises: f3a1d8c6b2e4
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d2c9f4b8e1'
down_revision: Union[str, Sequence[str], None] = 'f3a1d8c6b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'claim_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('decision_score', sa.Numeric(5, 2), nullable=False),
        sa.Column('expected_roi', sa.Numeric(10, 2), nullable=True),
        sa.Column('potential_recovery', sa.Numeric(12, 2), nullable=False),
        sa.Column('estimated_effort_cost', sa.Numeric(12, 2), nullable=False),
        sa.Column(
            'recommended_action',
            sa.Enum(
                'APPEAL', 'UPLOAD_DOCUMENTATION', 'AWAIT_AUTHORIZATION', 'MONITOR', 'WRITE_OFF',
                name='decisionaction',
            ),
            nullable=False,
        ),
        sa.Column('reasoning', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Numeric(5, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_claim_decisions_organization_id'), 'claim_decisions', ['organization_id'])
    op.create_index(op.f('ix_claim_decisions_claim_id'), 'claim_decisions', ['claim_id'])
    op.create_index(op.f('ix_claim_decisions_recommended_action'), 'claim_decisions', ['recommended_action'])

    op.create_table(
        'payer_statistics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('payer_id', sa.Integer(), nullable=False),
        sa.Column('average_payment_time', sa.Float(), nullable=True),
        sa.Column('appeal_success_rate', sa.Float(), nullable=True),
        sa.Column('average_recovery', sa.Numeric(12, 2), nullable=True),
        sa.Column('documentation_score', sa.Float(), nullable=True),
        sa.Column('average_denial_rate', sa.Float(), nullable=True),
        sa.Column('timely_filing_days', sa.Integer(), nullable=True),
        sa.Column('sample_size', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['payer_id'], ['payers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'payer_id', name='uq_payer_statistics_org_payer'),
    )
    op.create_index(op.f('ix_payer_statistics_organization_id'), 'payer_statistics', ['organization_id'])
    op.create_index(op.f('ix_payer_statistics_payer_id'), 'payer_statistics', ['payer_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_payer_statistics_payer_id'), table_name='payer_statistics')
    op.drop_index(op.f('ix_payer_statistics_organization_id'), table_name='payer_statistics')
    op.drop_table('payer_statistics')

    op.drop_index(op.f('ix_claim_decisions_recommended_action'), table_name='claim_decisions')
    op.drop_index(op.f('ix_claim_decisions_claim_id'), table_name='claim_decisions')
    op.drop_index(op.f('ix_claim_decisions_organization_id'), table_name='claim_decisions')
    op.drop_table('claim_decisions')

    sa.Enum(name='decisionaction').drop(op.get_bind(), checkfirst=True)
