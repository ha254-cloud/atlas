"""sprint 11 - add needs_review to claim_analyses, extend claimeventtype enum

Revision ID: f1a3c7e9b2d5
Revises: b4f8e2a6c9d3
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a3c7e9b2d5'
down_revision: Union[str, Sequence[str], None] = 'b4f8e2a6c9d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # New claim timeline milestones (Sprint 11 - Real AI Claim Analysis):
    # analysis start (previously only completion was recorded) and decision
    # engine output. Safe to run inside a transaction on Postgres 12+ (this
    # project runs 16), same as the appealstatus enum extension above.
    op.execute("ALTER TYPE claimeventtype ADD VALUE IF NOT EXISTS 'ANALYSIS_STARTED'")
    op.execute("ALTER TYPE claimeventtype ADD VALUE IF NOT EXISTS 'DECISION_GENERATED'")

    # Pre-existing gap found during Sprint 11 investigation: app/models/claim_event.py
    # has had a DOCUMENT_UPLOADED member (used for real by app/documents/service.py)
    # since document upload was built, but no prior migration ever added it to the
    # actual Postgres enum type - recording a document-uploaded timeline event
    # against a real Postgres database would fail with "invalid input value for
    # enum claimeventtype". SQLite-backed tests never caught this because SQLite
    # doesn't enforce native enum constraints. Fixing it here since it's the same
    # enum this migration is already touching.
    op.execute("ALTER TYPE claimeventtype ADD VALUE IF NOT EXISTS 'DOCUMENT_UPLOADED'")

    op.add_column(
        'claim_analyses',
        sa.Column('needs_review', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.alter_column('claim_analyses', 'needs_review', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('claim_analyses', 'needs_review')
    # Postgres cannot remove values from an existing enum type; the added
    # claimeventtype values are left in place on downgrade.
