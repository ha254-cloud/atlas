"""add validation engine: claim_validation_issues table + claim authorization fields

Revision ID: e6c1a9f4b2d7
Revises: b7e4d9a2c8f1
Create Date: 2026-07-23 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6c1a9f4b2d7'
down_revision: Union[str, Sequence[str], None] = 'b7e4d9a2c8f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('claims', sa.Column('authorization_number', sa.String(length=100), nullable=True))
    op.add_column('claims', sa.Column('authorization_expiration', sa.Date(), nullable=True))

    op.create_table(
        'claim_validation_issues',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('field', sa.String(length=100), nullable=False),
        sa.Column('message', sa.String(length=500), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_claim_validation_issues_organization_id'), 'claim_validation_issues', ['organization_id'], unique=False)
    op.create_index(op.f('ix_claim_validation_issues_claim_id'), 'claim_validation_issues', ['claim_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_claim_validation_issues_claim_id'), table_name='claim_validation_issues')
    op.drop_index(op.f('ix_claim_validation_issues_organization_id'), table_name='claim_validation_issues')
    op.drop_table('claim_validation_issues')

    op.drop_column('claims', 'authorization_expiration')
    op.drop_column('claims', 'authorization_number')
