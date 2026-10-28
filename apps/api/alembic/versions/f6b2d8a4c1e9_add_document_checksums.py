"""add document checksums

Revision ID: f6b2d8a4c1e9
Revises: e9a4c7b2d6f1
Create Date: 2026-08-02 00:00:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f6b2d8a4c1e9"
down_revision: str | Sequence[str] | None = "e9a4c7b2d6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("checksum", sa.String(length=64), nullable=True))
    connection = op.get_bind()
    documents = sa.table(
        "documents",
        sa.column("id", sa.Integer()),
        sa.column("checksum", sa.String(length=64)),
    )
    for document_id in connection.execute(sa.select(documents.c.id)).scalars():
        connection.execute(
            documents.update()
            .where(documents.c.id == document_id)
            .values(checksum=f"legacy-{document_id:057d}")
        )
    op.alter_column("documents", "checksum", nullable=False)
    op.create_unique_constraint(
        "uq_documents_org_claim_checksum",
        "documents",
        ["organization_id", "claim_id", "checksum"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_org_claim_checksum", "documents", type_="unique")
    op.drop_column("documents", "checksum")