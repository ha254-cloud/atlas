"""Add immutable document versions and extraction provenance.

Revision ID: a2d7e4c9f1b6
Revises: f0c8a3d6e1b4
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2d7e4c9f1b6"
down_revision: str | Sequence[str] | None = "f0c8a3d6e1b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("predecessor_version_id", sa.Integer(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extractor_name", sa.String(length=100), nullable=False),
        sa.Column("extractor_version", sa.String(length=100), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["predecessor_version_id"],
            ["document_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_document_version",
        ),
    )
    op.create_index(
        op.f("ix_document_versions_document_id"),
        "document_versions",
        ["document_id"],
    )
    op.create_index(
        op.f("ix_document_versions_organization_id"),
        "document_versions",
        ["organization_id"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO document_versions (
                organization_id, document_id, predecessor_version_id,
                version_number, reason, created_by_id, filename, storage_path,
                content_type, file_size, source_checksum, extracted_text,
                extractor_name, extractor_version, extracted_at, created_at, updated_at
            )
            SELECT
                organization_id, id, NULL, 1, 'legacy document backfill',
                uploaded_by_id, filename, storage_path, content_type, file_size,
                checksum, extracted_text, 'legacy-unrecorded', 'unknown',
                NULL, created_at, updated_at
            FROM documents
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_versions_organization_id"),
        table_name="document_versions",
    )
    op.drop_index(
        op.f("ix_document_versions_document_id"),
        table_name="document_versions",
    )
    op.drop_table("document_versions")
    op.drop_column("documents", "current_version")
