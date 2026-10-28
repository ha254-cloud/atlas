"""Link appeals to generated PDF documents.

Revision ID: fa3b5d7e9c2a
Revises: f9a2c4e6b8d1
Create Date: 2026-08-01 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "fa3b5d7e9c2a"
down_revision: str | Sequence[str] | None = "f9a2c4e6b8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("appeals", sa.Column("pdf_document_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_appeals_pdf_document_id_documents",
        "appeals",
        "documents",
        ["pdf_document_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_appeals_pdf_document_id_documents",
        "appeals",
        type_="foreignkey",
    )
    op.drop_column("appeals", "pdf_document_id")
