"""Add durable workflow events and event-linked execution history.

Revision ID: a9c3e7f2d5b8
Revises: f7a2c9d4e6b1
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a9c3e7f2d5b8"
down_revision: str | Sequence[str] | None = "f7a2c9d4e6b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE workflowsteptype ADD VALUE IF NOT EXISTS 'PUBLISH_EVENT'")
    for table_name in (
        "workflow_definitions",
        "workflow_steps",
        "workflow_executions",
        "workflow_step_executions",
    ):
        for column_name in ("created_at", "updated_at"):
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                existing_nullable=False,
            )
    op.add_column(
        "workflow_definitions",
        sa.Column("trigger_conditions", sa.Text(), nullable=True),
    )
    op.alter_column(
        "workflow_executions",
        "claim_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "workflow_executions",
        sa.Column("trigger_event", sa.String(100), nullable=True),
    )
    op.add_column(
        "workflow_executions",
        sa.Column("trigger_event_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "workflow_executions",
        sa.Column(
            "trigger_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "workflow_executions",
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_workflow_executions_trigger_event",
        "workflow_executions",
        ["trigger_event"],
    )
    op.create_index(
        "ix_workflow_executions_trigger_event_id",
        "workflow_executions",
        ["trigger_event_id"],
    )
    op.create_unique_constraint(
        "uq_workflow_executions_workflow_trigger_event",
        "workflow_executions",
        ["workflow_id", "trigger_event_id"],
    )

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organization_id",
            "event_id",
            name="uq_workflow_events_org_event_id",
        ),
    )
    for column in ("organization_id", "event_type", "status", "correlation_id"):
        op.create_index(
            f"ix_workflow_events_{column}",
            "workflow_events",
            [column],
        )


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely while dependent rows
    # may exist. PUBLISH_EVENT remains inert after the schema rollback.
    op.drop_table("workflow_events")
    op.drop_constraint(
        "uq_workflow_executions_workflow_trigger_event",
        "workflow_executions",
        type_="unique",
    )
    op.drop_index(
        "ix_workflow_executions_trigger_event_id",
        table_name="workflow_executions",
    )
    op.drop_index(
        "ix_workflow_executions_trigger_event",
        table_name="workflow_executions",
    )
    for column in ("duration_ms", "trigger_payload", "trigger_event_id", "trigger_event"):
        op.drop_column("workflow_executions", column)
    orphaned = op.get_bind().execute(
        sa.text("SELECT count(*) FROM workflow_executions WHERE claim_id IS NULL")
    ).scalar_one()
    if orphaned:
        raise RuntimeError(
            "Cannot restore required workflow_executions.claim_id while "
            "non-claim executions exist"
        )
    op.alter_column(
        "workflow_executions",
        "claim_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("workflow_definitions", "trigger_conditions")
    for table_name in (
        "workflow_definitions",
        "workflow_steps",
        "workflow_executions",
        "workflow_step_executions",
    ):
        for column_name in ("created_at", "updated_at"):
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                server_default=None,
                existing_nullable=False,
            )