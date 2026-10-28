"""add filename and error_message to import_jobs

Revision ID: b7e4d9a2c8f1
Revises: a1d4f6c9b0e3
Create Date: 2026-07-21 17:00:00.000000

Backfills columns that were present in the ImportJob model and in the
baseline migration's source, but were never actually applied to the live
database — the baseline migration file was edited after it had already run,
so `CREATE TABLE import_jobs` never included these two columns. This
migration brings the real schema in line with the model.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e4d9a2c8f1'
down_revision: Union[str, Sequence[str], None] = 'a1d4f6c9b0e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("import_jobs")}

    if "filename" not in existing_columns:
        op.add_column(
            "import_jobs",
            sa.Column("filename", sa.String(length=500), nullable=True),
        )

    if "error_message" not in existing_columns:
        op.add_column(
            "import_jobs",
            sa.Column("error_message", sa.String(length=1000), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("import_jobs", "error_message")
    op.drop_column("import_jobs", "filename")
