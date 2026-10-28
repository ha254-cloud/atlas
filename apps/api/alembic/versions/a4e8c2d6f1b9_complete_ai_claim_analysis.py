"""Complete the production AI claim analysis record.

Revision ID: a4e8c2d6f1b9
Revises: c8f4e2a1b7d9
Create Date: 2026-08-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a4e8c2d6f1b9"
down_revision: Union[str, Sequence[str], None] = "c8f4e2a1b7d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE analysisstatus ADD VALUE IF NOT EXISTS 'RUNNING'")
    op.execute("ALTER TYPE claimeventtype ADD VALUE IF NOT EXISTS 'AI_ANALYSIS_FAILED'")

    op.add_column(
        "claim_analyses",
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "claim_analyses",
        sa.Column("priority", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "claim_analyses",
        sa.Column(
            "required_documents",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "claim_analyses",
        sa.Column("model", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "claim_analyses",
        sa.Column("prompt_version", sa.String(length=20), nullable=True),
    )
    op.alter_column("claim_analyses", "required_documents", server_default=None)


def downgrade() -> None:
    op.drop_column("claim_analyses", "prompt_version")
    op.drop_column("claim_analyses", "model")
    op.drop_column("claim_analyses", "required_documents")
    op.drop_column("claim_analyses", "priority")
    op.drop_column("claim_analyses", "risk_score")
