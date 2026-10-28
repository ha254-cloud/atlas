"""add severity/recoverability/richer intelligence fields to denial_codes

Revision ID: a1f4d7c2b8e5
Revises: f7c2b6a9d4e1
Create Date: 2026-07-24 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.ai.denial_code_seed_data import DENIAL_CODE_SEED_DATA


# revision identifiers, used by Alembic.
revision: str = 'a1f4d7c2b8e5'
down_revision: Union[str, Sequence[str], None] = 'f7c2b6a9d4e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


denial_code_severity_enum = sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='denialcodeseverity')
denial_code_recoverability_enum = sa.Enum('LOW', 'MEDIUM', 'HIGH', name='denialcoderecoverability')


def upgrade() -> None:
    """Upgrade schema."""
    denial_code_severity_enum.create(op.get_bind(), checkfirst=True)
    denial_code_recoverability_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('denial_codes', sa.Column('severity', denial_code_severity_enum, nullable=True))
    op.add_column(
        'denial_codes',
        sa.Column('recoverability', denial_code_recoverability_enum, nullable=True),
    )
    op.add_column('denial_codes', sa.Column('typical_recovery_rate', sa.Float(), nullable=True))
    op.add_column('denial_codes', sa.Column('required_documents', sa.JSON(), nullable=True))
    op.add_column('denial_codes', sa.Column('typical_resolution_days', sa.Integer(), nullable=True))
    op.add_column('denial_codes', sa.Column('common_payers', sa.JSON(), nullable=True))
    op.add_column('denial_codes', sa.Column('references', sa.JSON(), nullable=True))

    denial_codes_table = sa.table(
        'denial_codes',
        sa.column('code', sa.String),
        sa.column('severity', sa.String),
        sa.column('recoverability', sa.String),
        sa.column('typical_recovery_rate', sa.Float),
        sa.column('required_documents', sa.JSON),
        sa.column('typical_resolution_days', sa.Integer),
        sa.column('common_payers', sa.JSON),
        sa.column('references', sa.JSON),
    )

    bind = op.get_bind()
    for entry in DENIAL_CODE_SEED_DATA:
        bind.execute(
            denial_codes_table.update()
            .where(denial_codes_table.c.code == entry["code"])
            .values(
                severity=entry["severity"].upper() if entry.get("severity") else None,
                recoverability=(
                    entry["recoverability"].upper() if entry.get("recoverability") else None
                ),
                typical_recovery_rate=entry.get("typical_recovery_rate"),
                required_documents=entry.get("required_documents"),
                typical_resolution_days=entry.get("typical_resolution_days"),
                common_payers=entry.get("common_payers"),
                references=entry.get("references"),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('denial_codes', 'references')
    op.drop_column('denial_codes', 'common_payers')
    op.drop_column('denial_codes', 'typical_resolution_days')
    op.drop_column('denial_codes', 'required_documents')
    op.drop_column('denial_codes', 'typical_recovery_rate')
    op.drop_column('denial_codes', 'recoverability')
    op.drop_column('denial_codes', 'severity')

    denial_code_recoverability_enum.drop(op.get_bind(), checkfirst=True)
    denial_code_severity_enum.drop(op.get_bind(), checkfirst=True)
