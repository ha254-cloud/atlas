"""Add governed document classification state.

Revision ID: c4f9a2e7b1d6
Revises: b3e8f5a1c7d9
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4f9a2e7b1d6"
down_revision: str | Sequence[str] | None = "b3e8f5a1c7d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

document_type_enum = postgresql.ENUM(
    "OPERATIVE_REPORT",
    "IMAGING",
    "REFERRAL",
    "LAB_RESULTS",
    "AUTHORIZATION",
    "PHYSICIAN_NOTES",
    "OTHER",
    name="documenttype",
    create_type=False,
)
review_status_enum = postgresql.ENUM(
    "PENDING",
    "ACCEPTED",
    "CORRECTED",
    name="documentclassificationreviewstatus",
    create_type=False,
)


def upgrade() -> None:
    review_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column(
            "extraction_status", sa.String(length=20), server_default="unrecorded", nullable=False
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "extraction_method", sa.String(length=30), server_default="unknown", nullable=False
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "extraction_engine", sa.String(length=100), server_default="unknown", nullable=False
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "extraction_engine_version",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "documents", sa.Column("extraction_confidence", sa.Numeric(5, 4), nullable=True)
    )
    op.add_column(
        "documents",
        sa.Column("predicted_document_type", document_type_enum, nullable=True),
    )
    op.add_column(
        "documents", sa.Column("classification_confidence", sa.Numeric(5, 4), nullable=True)
    )
    op.add_column(
        "documents", sa.Column("classification_provider", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "documents", sa.Column("classification_model", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "documents",
        sa.Column("classification_prompt_version", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "documents", sa.Column("classification_review_status", review_status_enum, nullable=True)
    )
    op.add_column(
        "documents", sa.Column("classification_reviewed_by_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "documents",
        sa.Column("classification_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("classification_review_reason", sa.String(length=500), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_classification_reviewed_by_id_users",
        "documents",
        "users",
        ["classification_reviewed_by_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_documents_classification_reviewed_by_id_users", "documents", type_="foreignkey"
    )
    op.drop_column("documents", "classification_review_reason")
    op.drop_column("documents", "classification_reviewed_at")
    op.drop_column("documents", "classification_reviewed_by_id")
    op.drop_column("documents", "classification_review_status")
    op.drop_column("documents", "classification_prompt_version")
    op.drop_column("documents", "classification_model")
    op.drop_column("documents", "classification_provider")
    op.drop_column("documents", "classification_confidence")
    op.drop_column("documents", "predicted_document_type")
    op.drop_column("documents", "extraction_confidence")
    op.drop_column("documents", "extraction_engine_version")
    op.drop_column("documents", "extraction_engine")
    op.drop_column("documents", "extraction_method")
    op.drop_column("documents", "extraction_status")
    review_status_enum.drop(op.get_bind(), checkfirst=True)