"""Add append-only integration credential versions.

Revision ID: b2e4f6a8c1d3
Revises: a9c3e7f2d5b8
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b2e4f6a8c1d3"
down_revision: str | Sequence[str] | None = "a9c3e7f2d5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_credential_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "integration_id",
            sa.Integer(),
            sa.ForeignKey("integrations.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("credential_kind", sa.String(30), nullable=False),
        sa.Column(
            "fingerprints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "integration_id",
            "version",
            name="uq_integration_credential_versions_integration_version",
        ),
    )
    op.create_index(
        "ix_integration_credential_versions_integration_id",
        "integration_credential_versions",
        ["integration_id"],
    )
    op.create_index(
        "ix_integration_credential_versions_correlation_id",
        "integration_credential_versions",
        ["correlation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integration_credential_versions_correlation_id",
        table_name="integration_credential_versions",
    )
    op.drop_index(
        "ix_integration_credential_versions_integration_id",
        table_name="integration_credential_versions",
    )
    op.drop_table("integration_credential_versions")
