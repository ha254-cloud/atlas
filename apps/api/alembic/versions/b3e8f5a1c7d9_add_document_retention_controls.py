"""Add document retention state and append-only holds.

Revision ID: b3e8f5a1c7d9
Revises: a2d7e4c9f1b6
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b3e8f5a1c7d9"
down_revision: str | Sequence[str] | None = "a2d7e4c9f1b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

retention_status_enum = postgresql.ENUM(
    "ACTIVE",
    "ARCHIVED",
    "PENDING_DELETE",
    "DELETED",
    name="documentretentionstatus",
    create_type=False,
)
hold_type_enum = postgresql.ENUM(
    "LEGAL",
    "CLINICAL",
    name="documentholdtype",
    create_type=False,
)


def upgrade() -> None:
    retention_status_enum.create(op.get_bind(), checkfirst=True)
    hold_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column(
            "retention_status",
            retention_status_enum,
            server_default="ACTIVE",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_documents_retention_status"),
        "documents",
        ["retention_status"],
    )

    op.create_table(
        "document_holds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("hold_type", hold_type_enum, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("recorded_by_id", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "hold_type",
            "version",
            name="uq_document_holds_document_type_version",
        ),
    )
    op.create_index(
        op.f("ix_document_holds_document_id"),
        "document_holds",
        ["document_id"],
    )
    op.create_index(
        op.f("ix_document_holds_organization_id"),
        "document_holds",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_document_holds_correlation_id"),
        "document_holds",
        ["correlation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_holds_correlation_id"),
        table_name="document_holds",
    )
    op.drop_index(
        op.f("ix_document_holds_organization_id"),
        table_name="document_holds",
    )
    op.drop_index(
        op.f("ix_document_holds_document_id"),
        table_name="document_holds",
    )
    op.drop_table("document_holds")
    op.drop_index(op.f("ix_documents_retention_status"), table_name="documents")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "archived_at")
    op.drop_column("documents", "retention_status")
    hold_type_enum.drop(op.get_bind(), checkfirst=True)
    retention_status_enum.drop(op.get_bind(), checkfirst=True)
