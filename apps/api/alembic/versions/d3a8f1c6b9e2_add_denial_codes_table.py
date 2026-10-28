"""add denial_codes table (denial knowledge base) + seed standard CARC codes

Revision ID: d3a8f1c6b9e2
Revises: a9c3e5f7b1d4
Create Date: 2026-07-24 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.ai.denial_code_seed_data import DENIAL_CODE_SEED_DATA


# revision identifiers, used by Alembic.
revision: str = 'd3a8f1c6b9e2'
down_revision: Union[str, Sequence[str], None] = 'a9c3e5f7b1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The `denialtype` enum type already exists (created in the baseline
# migration, extended in b3f9e1c7a4d2) — reuse it with create_type=False
# instead of letting SQLAlchemy try (and fail) to CREATE TYPE again.
# NOTE: generic sa.Enum(create_type=False) silently ignores create_type
# (that kwarg only actually does anything on the postgres-dialect-specific
# postgresql.ENUM class) — must use postgresql.ENUM here, not sa.Enum.
_denial_category_enum = postgresql.ENUM(
    'ELIGIBILITY', 'CODING', 'DUPLICATE', 'PRIOR_AUTH', 'TIMELY_FILING',
    'MEDICAL_NECESSITY', 'DOCUMENTATION', 'MODIFIER_ERROR',
    'NON_COVERED_SERVICE', 'COORDINATION_OF_BENEFITS', 'OTHER',
    name='denialtype',
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'denial_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('category', _denial_category_enum, nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('recovery_strategy', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_denial_codes_code'), 'denial_codes', ['code'], unique=True)

    denial_codes_table = sa.table(
        'denial_codes',
        sa.column('code', sa.String),
        sa.column('category', sa.String),
        sa.column('description', sa.String),
        sa.column('recovery_strategy', sa.String),
    )
    op.bulk_insert(denial_codes_table, DENIAL_CODE_SEED_DATA)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_denial_codes_code'), table_name='denial_codes')
    op.drop_table('denial_codes')
