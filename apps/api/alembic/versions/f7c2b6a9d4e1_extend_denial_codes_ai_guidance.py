"""extend denial_codes with ai_guidance + is_active, add CO151

Revision ID: f7c2b6a9d4e1
Revises: d3a8f1c6b9e2
Create Date: 2026-07-24 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.ai.denial_code_seed_data import DENIAL_CODE_SEED_DATA


# revision identifiers, used by Alembic.
revision: str = 'f7c2b6a9d4e1'
down_revision: Union[str, Sequence[str], None] = 'd3a8f1c6b9e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Codes already seeded by d3a8f1c6b9e2 — everything else in
# DENIAL_CODE_SEED_DATA is new as of this migration (currently just CO151)
# and needs a fresh INSERT rather than an UPDATE.
_PRE_EXISTING_CODES = {
    "CO16", "CO18", "CO29", "CO50", "CO97", "CO4", "CO11", "CO22",
    "CO27", "CO31", "CO45", "CO96", "CO109", "CO197", "PR1", "PR2",
}


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('denial_codes', sa.Column('ai_guidance', sa.Text(), nullable=True))
    op.add_column(
        'denial_codes',
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index(op.f('ix_denial_codes_category'), 'denial_codes', ['category'], unique=False)

    denial_codes_table = sa.table(
        'denial_codes',
        sa.column('code', sa.String),
        sa.column('category', sa.String),
        sa.column('description', sa.String),
        sa.column('recovery_strategy', sa.String),
        sa.column('ai_guidance', sa.Text),
    )

    bind = op.get_bind()
    existing_codes = {
        row[0]
        for row in bind.execute(sa.select(denial_codes_table.c.code))
    }
    for entry in DENIAL_CODE_SEED_DATA:
        if entry["code"] in existing_codes:
            bind.execute(
                denial_codes_table.update()
                .where(denial_codes_table.c.code == entry["code"])
                .values(ai_guidance=entry["ai_guidance"])
            )
        else:
            bind.execute(
                denial_codes_table.insert().values(
                    code=entry["code"],
                    category=entry["category"],
                    description=entry["description"],
                    recovery_strategy=entry["recovery_strategy"],
                    ai_guidance=entry["ai_guidance"],
                )
            )


def downgrade() -> None:
    """Downgrade schema."""
    denial_codes_table = sa.table('denial_codes', sa.column('code', sa.String))
    bind = op.get_bind()
    bind.execute(denial_codes_table.delete().where(denial_codes_table.c.code == "CO151"))

    op.drop_index(op.f('ix_denial_codes_category'), table_name='denial_codes')
    op.drop_column('denial_codes', 'is_active')
    op.drop_column('denial_codes', 'ai_guidance')
