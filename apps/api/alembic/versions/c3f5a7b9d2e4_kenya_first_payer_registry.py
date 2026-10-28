"""Add Kenya-first payer registry capabilities.

Revision ID: c3f5a7b9d2e4
Revises: b2e4f6a8c1d3
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3f5a7b9d2e4"
down_revision: str | Sequence[str] | None = "b2e4f6a8c1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payers", sa.Column("country", sa.String(2), nullable=False, server_default="KE"))
    op.add_column(
        "payers",
        sa.Column("submission_method", sa.String(30), nullable=False, server_default="manual"),
    )
    op.add_column(
        "payers",
        sa.Column("status_method", sa.String(30), nullable=False, server_default="manual"),
    )
    op.add_column(
        "payers",
        sa.Column("payment_method", sa.String(30), nullable=False, server_default="report"),
    )
    op.add_column("payers", sa.Column("portal_url", sa.String(2048), nullable=True))
    op.add_column("payers", sa.Column("api_url", sa.String(2048), nullable=True))
    op.add_column("payers", sa.Column("submission_email", sa.String(320), nullable=True))
    op.add_column(
        "payers", sa.Column("supports_api", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "payers", sa.Column("supports_sftp", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "payers", sa.Column("supports_email", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "payers", sa.Column("supports_manual", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column("payers", sa.Column("connector_name", sa.String(50), nullable=True))
    op.add_column(
        "payers",
        sa.Column("integration_id", sa.Integer(), sa.ForeignKey("integrations.id"), nullable=True),
    )
    op.add_column(
        "payers", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.create_index("ix_payers_integration_id", "payers", ["integration_id"])
    for source in ("CSV", "EXCEL", "PORTAL_EXPORT", "EMAIL_REPORT"):
        op.execute(f"ALTER TYPE paymentsource ADD VALUE IF NOT EXISTS '{source}'")


def downgrade() -> None:
    op.drop_index("ix_payers_integration_id", table_name="payers")
    for column in (
        "is_active",
        "integration_id",
        "connector_name",
        "supports_manual",
        "supports_email",
        "supports_sftp",
        "supports_api",
        "submission_email",
        "api_url",
        "portal_url",
        "payment_method",
        "status_method",
        "submission_method",
        "country",
    ):
        op.drop_column("payers", column)
