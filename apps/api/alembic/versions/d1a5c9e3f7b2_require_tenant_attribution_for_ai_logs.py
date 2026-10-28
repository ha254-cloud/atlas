"""Require tenant attribution for AI and agent execution logs.

Revision ID: d1a5c9e3f7b2
Revises: b8e4c2f7a1d9
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1a5c9e3f7b2"
down_revision: str | Sequence[str] | None = "b8e4c2f7a1d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_from_claim(table_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE {table_name} AS log
            SET organization_id = claim.organization_id
            FROM claims AS claim
            WHERE log.claim_id = claim.id
              AND log.organization_id IS NULL
            """
        )
    )
    remaining = op.get_bind().execute(
        sa.text(f"SELECT count(*) FROM {table_name} WHERE organization_id IS NULL")
    ).scalar_one()
    if remaining:
        raise RuntimeError(
            f"Cannot require {table_name}.organization_id: "
            f"{remaining} unattributed rows cannot be inferred from claim_id"
        )


def upgrade() -> None:
    for table_name in ("ai_call_logs", "agent_execution_logs"):
        _backfill_from_claim(table_name)
        op.alter_column(
            table_name,
            "organization_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    for table_name in ("agent_execution_logs", "ai_call_logs"):
        op.alter_column(
            table_name,
            "organization_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
