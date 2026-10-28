"""fix missing server_default now() on created_at/updated_at for tables
created without it (email_verification_tokens, password_reset_tokens,
invitations, claim_analyses, appeal_versions) — the SQLAlchemy models all
declare server_default=func.now() via TimestampMixin, but the original
create_table() migrations for these five tables omitted it, so real
Postgres inserts that don't explicitly set created_at/updated_at fail with
a NOT NULL violation (only masked in tests because SQLite fixtures build
tables via Base.metadata.create_all(), which does honor the model default).

Revision ID: a9c3e5f7b1d4
Revises: e7f1c9a3b5d8
Create Date: 2026-07-23 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9c3e5f7b1d4'
down_revision: Union[str, Sequence[str], None] = 'e7f1c9a3b5d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    'email_verification_tokens',
    'password_reset_tokens',
    'invitations',
    'claim_analyses',
    'appeal_versions',
]


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        op.alter_column(table, 'created_at', server_default=sa.text('now()'))
        op.alter_column(table, 'updated_at', server_default=sa.text('now()'))


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        op.alter_column(table, 'updated_at', server_default=None)
        op.alter_column(table, 'created_at', server_default=None)
