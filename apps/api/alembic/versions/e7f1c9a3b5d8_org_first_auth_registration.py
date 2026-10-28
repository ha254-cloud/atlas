"""org-first auth: organization fields, email verification, password reset, invitations

Revision ID: e7f1c9a3b5d8
Revises: c4a2f8e6d1b9
Create Date: 2026-07-23 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e7f1c9a3b5d8'
down_revision: Union[str, Sequence[str], None] = 'c4a2f8e6d1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # New canonical roles alongside the existing legacy ones.
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'MANAGER'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'REVENUE_ANALYST'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'APPEALS_SPECIALIST'")

    op.add_column('organizations', sa.Column('slug', sa.String(length=255), nullable=True))
    op.add_column('organizations', sa.Column('organization_type', sa.String(length=50), nullable=True))
    op.add_column('organizations', sa.Column('country', sa.String(length=100), nullable=True))
    op.add_column('organizations', sa.Column('plan', sa.String(length=50), nullable=False, server_default='trial'))
    op.add_column('organizations', sa.Column('status', sa.String(length=50), nullable=False, server_default='active'))
    op.alter_column('organizations', 'plan', server_default=None)
    op.alter_column('organizations', 'status', server_default=None)
    op.create_unique_constraint('uq_organizations_slug', 'organizations', ['slug'])

    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('users', 'email_verified', server_default=None)

    op.create_table(
        'email_verification_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_email_verification_tokens_user_id'), 'email_verification_tokens', ['user_id'])
    op.create_index(op.f('ix_email_verification_tokens_token'), 'email_verification_tokens', ['token'])

    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'])
    op.create_index(op.f('ix_password_reset_tokens_token'), 'password_reset_tokens', ['token'])

    op.create_table(
        'invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', postgresql.ENUM('ADMIN', 'BILLER', 'AUDITOR', 'VIEWER', 'MANAGER', 'REVENUE_ANALYST', 'APPEALS_SPECIALIST', name='userrole', create_type=False), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('invited_by', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_invitations_organization_id'), 'invitations', ['organization_id'])
    op.create_index(op.f('ix_invitations_email'), 'invitations', ['email'])
    op.create_index(op.f('ix_invitations_token'), 'invitations', ['token'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_invitations_token'), table_name='invitations')
    op.drop_index(op.f('ix_invitations_email'), table_name='invitations')
    op.drop_index(op.f('ix_invitations_organization_id'), table_name='invitations')
    op.drop_table('invitations')

    op.drop_index(op.f('ix_password_reset_tokens_token'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')

    op.drop_index(op.f('ix_email_verification_tokens_token'), table_name='email_verification_tokens')
    op.drop_index(op.f('ix_email_verification_tokens_user_id'), table_name='email_verification_tokens')
    op.drop_table('email_verification_tokens')

    op.drop_column('users', 'email_verified')

    op.drop_constraint('uq_organizations_slug', 'organizations', type_='unique')
    op.drop_column('organizations', 'status')
    op.drop_column('organizations', 'plan')
    op.drop_column('organizations', 'country')
    op.drop_column('organizations', 'organization_type')
    op.drop_column('organizations', 'slug')
    # Postgres cannot remove values from an existing enum type; the added
    # userrole values are left in place on downgrade.
