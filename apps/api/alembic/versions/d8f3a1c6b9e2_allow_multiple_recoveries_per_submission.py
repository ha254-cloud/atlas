"""Allow multiple recoveries per appeal submission.

Revision ID: d8f3a1c6b9e2
Revises: c3f5a7b9d2e4
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8f3a1c6b9e2"
down_revision: str | Sequence[str] | None = "c3f5a7b9d2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_recoveries_submission_id",
        "recoveries",
        type_="unique",
    )


def downgrade() -> None:
    duplicate_submission = op.get_bind().execute(sa.text("""
        SELECT submission_id
        FROM recoveries
        WHERE submission_id IS NOT NULL
        GROUP BY submission_id
        HAVING count(*) > 1
        LIMIT 1
    """)).scalar_one_or_none()
    if duplicate_submission is not None:
        raise RuntimeError(
            "Cannot restore one-recovery-per-submission constraint while "
            "multiple recoveries reference a submission"
        )
    op.create_unique_constraint(
        "uq_recoveries_submission_id",
        "recoveries",
        ["submission_id"],
    )
