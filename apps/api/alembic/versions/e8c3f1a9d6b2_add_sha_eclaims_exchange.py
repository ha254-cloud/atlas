"""Add tenant-scoped SHA eClaims exchange evidence.

Revision ID: e8c3f1a9d6b2
Revises: d4f7a2c6e9b3
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8c3f1a9d6b2"
down_revision: str | Sequence[str] | None = "d4f7a2c6e9b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sha_eclaim_exchanges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("initiated_by", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("ig_version", sa.String(length=20), nullable=False),
        sa.Column("bundle_identifier", sa.String(length=255), nullable=False),
        sa.Column("bundle_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("claim_response_id", sa.String(length=255), nullable=True),
        sa.Column("outcome", sa.String(length=50), nullable=True),
        sa.Column("workflow_state", sa.String(length=50), nullable=True),
        sa.Column("approved_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("response_sha256", sa.String(length=64), nullable=True),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("response_summary", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["initiated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_sha_eclaim_exchanges_id_org",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_sha_eclaim_exchanges_org_idempotency",
        ),
    )
    op.create_index(
        op.f("ix_sha_eclaim_exchanges_claim_id"),
        "sha_eclaim_exchanges",
        ["claim_id"],
    )
    op.create_index(
        op.f("ix_sha_eclaim_exchanges_correlation_id"),
        "sha_eclaim_exchanges",
        ["correlation_id"],
    )
    op.create_index(
        op.f("ix_sha_eclaim_exchanges_integration_id"),
        "sha_eclaim_exchanges",
        ["integration_id"],
    )
    op.create_index(
        op.f("ix_sha_eclaim_exchanges_organization_id"),
        "sha_eclaim_exchanges",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_sha_eclaim_exchanges_status"),
        "sha_eclaim_exchanges",
        ["status"],
    )

    op.create_table(
        "sha_eclaim_exchange_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exchange_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response_sha256", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=50), nullable=True),
        sa.Column("workflow_state", sa.String(length=50), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["exchange_id", "organization_id"],
            ["sha_eclaim_exchanges.id", "sha_eclaim_exchanges.organization_id"],
            name="fk_sha_exchange_events_exchange_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sha_eclaim_exchange_events_correlation_id"),
        "sha_eclaim_exchange_events",
        ["correlation_id"],
    )
    op.create_index(
        op.f("ix_sha_eclaim_exchange_events_exchange_id"),
        "sha_eclaim_exchange_events",
        ["exchange_id"],
    )
    op.create_index(
        op.f("ix_sha_eclaim_exchange_events_organization_id"),
        "sha_eclaim_exchange_events",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sha_eclaim_exchange_events_organization_id"),
        table_name="sha_eclaim_exchange_events",
    )
    op.drop_index(
        op.f("ix_sha_eclaim_exchange_events_exchange_id"),
        table_name="sha_eclaim_exchange_events",
    )
    op.drop_index(
        op.f("ix_sha_eclaim_exchange_events_correlation_id"),
        table_name="sha_eclaim_exchange_events",
    )
    op.drop_table("sha_eclaim_exchange_events")
    op.drop_index(
        op.f("ix_sha_eclaim_exchanges_status"),
        table_name="sha_eclaim_exchanges",
    )
    op.drop_index(
        op.f("ix_sha_eclaim_exchanges_organization_id"),
        table_name="sha_eclaim_exchanges",
    )
    op.drop_index(
        op.f("ix_sha_eclaim_exchanges_integration_id"),
        table_name="sha_eclaim_exchanges",
    )
    op.drop_index(
        op.f("ix_sha_eclaim_exchanges_correlation_id"),
        table_name="sha_eclaim_exchanges",
    )
    op.drop_index(
        op.f("ix_sha_eclaim_exchanges_claim_id"),
        table_name="sha_eclaim_exchanges",
    )
    op.drop_table("sha_eclaim_exchanges")
