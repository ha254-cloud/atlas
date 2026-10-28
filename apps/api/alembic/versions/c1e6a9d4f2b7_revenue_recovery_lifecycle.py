"""Add the revenue recovery lifecycle ledger.

Revision ID: c1e6a9d4f2b7
Revises: b9d4e7f2a6c1
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c1e6a9d4f2b7"
down_revision: str | Sequence[str] | None = "b9d4e7f2a6c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_state_values = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "APPROVED",
    "PARTIALLY_PAID",
    "OUTSTANDING",
    "APPEAL",
    "RECOVERED",
    "WRITTEN_OFF",
    "CLOSED",
)
_event_values = (
    "ACCOUNT_OPENED",
    "STATE_TRANSITIONED",
    "PAYMENT_CONFIRMED",
    "CONTRACT_ADJUSTMENT",
    "WRITE_OFF_APPROVED",
    "WRITE_OFF_REVERSED",
    "RESPONSIBILITY_ASSIGNED",
    "ACCOUNT_CLOSED",
    "ACCOUNT_REOPENED",
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    state_enum = postgresql.ENUM(*_state_values, name="recoverylifecyclestate", create_type=False)
    event_enum = postgresql.ENUM(*_event_values, name="recoveryeventtype", create_type=False)
    state_enum.create(bind, checkfirst=True)
    event_enum.create(bind, checkfirst=True)

    op.create_table(
        "recovery_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("state", state_enum, server_default="DRAFT", nullable=False),
        sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "claim_id", name="uq_recovery_account_org_claim"),
    )
    op.create_index("ix_recovery_accounts_organization_id", "recovery_accounts", ["organization_id"])
    op.create_index("ix_recovery_accounts_claim_id", "recovery_accounts", ["claim_id"])
    op.create_index("ix_recovery_accounts_assigned_user_id", "recovery_accounts", ["assigned_user_id"])

    op.create_table(
        "recovery_lifecycle_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("recovery_accounts.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", event_enum, nullable=False),
        sa.Column("from_state", state_enum, nullable=True),
        sa.Column("to_state", state_enum, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_type", sa.String(length=30), server_default="user", nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_recovery_lifecycle_event_amount"),
        sa.UniqueConstraint("account_id", "sequence", name="uq_recovery_lifecycle_event_sequence"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_recovery_lifecycle_event_idempotency",
        ),
    )
    op.create_index(
        "ix_recovery_lifecycle_events_organization_id",
        "recovery_lifecycle_events",
        ["organization_id"],
    )
    op.create_index("ix_recovery_lifecycle_events_account_id", "recovery_lifecycle_events", ["account_id"])
    op.create_index("ix_recovery_lifecycle_events_event_type", "recovery_lifecycle_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_recovery_lifecycle_events_event_type", table_name="recovery_lifecycle_events")
    op.drop_index("ix_recovery_lifecycle_events_account_id", table_name="recovery_lifecycle_events")
    op.drop_index("ix_recovery_lifecycle_events_organization_id", table_name="recovery_lifecycle_events")
    op.drop_table("recovery_lifecycle_events")
    op.drop_index("ix_recovery_accounts_assigned_user_id", table_name="recovery_accounts")
    op.drop_index("ix_recovery_accounts_claim_id", table_name="recovery_accounts")
    op.drop_index("ix_recovery_accounts_organization_id", table_name="recovery_accounts")
    op.drop_table("recovery_accounts")
    bind = op.get_bind()
    postgresql.ENUM(name="recoveryeventtype").drop(bind, checkfirst=True)
    postgresql.ENUM(name="recoverylifecyclestate").drop(bind, checkfirst=True)
