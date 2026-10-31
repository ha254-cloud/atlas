"""Add transactional domain event outbox.

Revision ID: 4a6d8e2c0f1b
Revises: 9f4d2c7a1b6e
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4a6d8e2c0f1b"
down_revision: str | Sequence[str] | None = "9f4d2c7a1b6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "domain_event_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'published', 'dead_letter')",
            name="ck_domain_event_outbox_status",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "ix_domain_event_outbox_dispatch",
        "domain_event_outbox",
        ["status", "available_at", "created_at"],
    )
    op.create_index(
        "ix_domain_event_outbox_organization_id",
        "domain_event_outbox",
        ["organization_id"],
    )
    op.create_index(
        "ix_domain_event_outbox_event_type",
        "domain_event_outbox",
        ["event_type"],
    )
    op.create_index(
        "ix_domain_event_outbox_correlation_id",
        "domain_event_outbox",
        ["correlation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_domain_event_outbox_correlation_id", table_name="domain_event_outbox")
    op.drop_index("ix_domain_event_outbox_event_type", table_name="domain_event_outbox")
    op.drop_index("ix_domain_event_outbox_organization_id", table_name="domain_event_outbox")
    op.drop_index("ix_domain_event_outbox_dispatch", table_name="domain_event_outbox")
    op.drop_table("domain_event_outbox")
