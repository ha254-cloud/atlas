"""expand claim_lines with billing detail fields and add claim_diagnoses table

Revision ID: c4d8f2a91b3e
Revises: 0252bb93ca78
Create Date: 2026-07-21 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d8f2a91b3e'
down_revision: Union[str, Sequence[str], None] = '0252bb93ca78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # claim_lines: rename procedure_code -> cpt_code, amount -> charge_amount,
    # drop diagnosis_code (moved to its own claim_diagnoses table), and add
    # the richer billing detail fields a production claim line needs.
    op.alter_column('claim_lines', 'procedure_code', new_column_name='cpt_code')
    op.alter_column('claim_lines', 'amount', new_column_name='charge_amount')
    op.add_column('claim_lines', sa.Column('modifier', sa.String(length=10), nullable=True))
    op.add_column('claim_lines', sa.Column('description', sa.String(length=255), nullable=True))
    op.add_column('claim_lines', sa.Column('units', sa.Integer(), nullable=False, server_default='1'))
    op.alter_column('claim_lines', 'units', server_default=None)
    op.add_column('claim_lines', sa.Column('allowed_amount', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('claim_lines', sa.Column('paid_amount', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('claim_lines', sa.Column('status', sa.String(length=50), nullable=True))
    op.drop_column('claim_lines', 'diagnosis_code')

    op.create_table(
        'claim_diagnoses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('icd_code', sa.String(length=20), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_claim_diagnoses_claim_id'), 'claim_diagnoses', ['claim_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_claim_diagnoses_claim_id'), table_name='claim_diagnoses')
    op.drop_table('claim_diagnoses')

    op.add_column('claim_lines', sa.Column('diagnosis_code', sa.String(length=20), nullable=False, server_default=''))
    op.alter_column('claim_lines', 'diagnosis_code', server_default=None)
    op.drop_column('claim_lines', 'status')
    op.drop_column('claim_lines', 'paid_amount')
    op.drop_column('claim_lines', 'allowed_amount')
    op.drop_column('claim_lines', 'units')
    op.drop_column('claim_lines', 'description')
    op.drop_column('claim_lines', 'modifier')
    op.alter_column('claim_lines', 'charge_amount', new_column_name='amount')
    op.alter_column('claim_lines', 'cpt_code', new_column_name='procedure_code')
