"""extend appealstatus enum, add appeal lifecycle columns, add appeal_versions table

Revision ID: c4a2f8e6d1b9
Revises: b3f9e1c7a4d2
Create Date: 2026-07-23 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a2f8e6d1b9'
down_revision: Union[str, Sequence[str], None] = 'b3f9e1c7a4d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # New appeal lifecycle states (review/approval gate before submission) —
    # safe to run inside a transaction on Postgres 12+ (this project runs 16).
    op.execute("ALTER TYPE appealstatus ADD VALUE IF NOT EXISTS 'REVIEW'")
    op.execute("ALTER TYPE appealstatus ADD VALUE IF NOT EXISTS 'APPROVED'")
    op.execute("ALTER TYPE appealstatus ADD VALUE IF NOT EXISTS 'REJECTED'")
    op.execute("ALTER TYPE appealstatus ADD VALUE IF NOT EXISTS 'CLOSED'")

    op.add_column('appeals', sa.Column('analysis_id', sa.Integer(), nullable=True))
    op.add_column('appeals', sa.Column('generated_by', sa.String(), nullable=True, server_default='ai'))
    op.add_column('appeals', sa.Column('submitted_by', sa.Integer(), nullable=True))
    op.add_column('appeals', sa.Column('confirmation_number', sa.String(), nullable=True))
    op.add_column('appeals', sa.Column('response_due_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('appeals', sa.Column('current_version', sa.Integer(), nullable=False, server_default='1'))
    op.alter_column('appeals', 'current_version', server_default=None)
    op.alter_column('appeals', 'generated_by', server_default=None)
    op.create_foreign_key(None, 'appeals', 'claim_analyses', ['analysis_id'], ['id'])
    op.create_foreign_key(None, 'appeals', 'users', ['submitted_by'], ['id'])

    op.create_table(
        'appeal_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('appeal_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('appeal_text', sa.Text(), nullable=False),
        sa.Column('sections', sa.JSON(), nullable=True),
        sa.Column('edited_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['appeal_id'], ['appeals.id']),
        sa.ForeignKeyConstraint(['edited_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_appeal_versions_organization_id'), 'appeal_versions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_appeal_versions_appeal_id'), 'appeal_versions', ['appeal_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_appeal_versions_appeal_id'), table_name='appeal_versions')
    op.drop_index(op.f('ix_appeal_versions_organization_id'), table_name='appeal_versions')
    op.drop_table('appeal_versions')
    op.drop_column('appeals', 'current_version')
    op.drop_column('appeals', 'response_due_date')
    op.drop_column('appeals', 'confirmation_number')
    op.drop_column('appeals', 'submitted_by')
    op.drop_column('appeals', 'generated_by')
    op.drop_column('appeals', 'analysis_id')
    # Postgres cannot remove values from an existing enum type; the added
    # appealstatus values are left in place on downgrade.
