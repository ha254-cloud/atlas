"""Add task intelligence tables.

Revision ID: e9a4c7b2d6f1
Revises: d8f3a1c6b9e2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e9a4c7b2d6f1"
down_revision: str | None = "d8f3a1c6b9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

task_department = sa.Enum(
    "CLAIMS", "APPEALS", "FINANCE", "REVENUE_MANAGEMENT", name="taskdepartment"
)
task_type = sa.Enum(
    "REVIEW_CLAIM",
    "UPLOAD_DOCUMENTS",
    "GENERATE_APPEAL",
    "APPROVE_APPEAL",
    "SUBMIT_APPEAL",
    "CHECK_PAYER_PORTAL",
    "CALL_PAYER",
    "UPLOAD_PAYMENT_REPORT",
    "VERIFY_PAYMENT",
    "RECONCILE_PAYMENT",
    "CLOSE_CLAIM",
    "ESCALATE",
    "FOLLOW_UP",
    "REQUEST_MISSING_DOCUMENTS",
    name="tasktype",
)
task_status = sa.Enum(
    "NEW",
    "ASSIGNED",
    "IN_PROGRESS",
    "WAITING",
    "COMPLETED",
    "OVERDUE",
    "CANCELLED",
    name="taskstatus",
)


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("department", task_department, nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("task_type", task_type, nullable=False),
        sa.Column("status", task_status, nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100", name="ck_tasks_priority_score"
        ),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["payer_id"], ["payers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "claim_id", "task_type", "sequence", name="uq_tasks_claim_action"
        ),
    )
    op.create_index(
        "ix_tasks_org_assignee_status_due",
        "tasks",
        ["organization_id", "assigned_to", "status", "due_date"],
    )
    op.create_index(
        "ix_tasks_org_priority_created",
        "tasks",
        ["organization_id", "priority_score", "created_at"],
    )
    for column in (
        "organization_id",
        "claim_id",
        "payer_id",
        "assigned_to",
        "task_type",
        "status",
        "due_date",
    ):
        op.create_index(f"ix_tasks_{column}", "tasks", [column])

    op.create_table(
        "task_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "task_id",
            "notification_type",
            "recipient_id",
            "level",
            name="uq_task_notification_delivery",
        ),
    )
    op.create_index(
        "ix_task_notifications_recipient_read",
        "task_notifications",
        ["organization_id", "recipient_id", "read_at"],
    )
    for column in ("organization_id", "task_id", "recipient_id"):
        op.create_index(f"ix_task_notifications_{column}", "task_notifications", [column])

    op.create_table(
        "user_task_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skill", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", "skill", name="uq_user_task_skill"),
    )
    for column in ("organization_id", "user_id", "skill"):
        op.create_index(f"ix_user_task_skills_{column}", "user_task_skills", [column])

    op.create_table(
        "task_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "task_id",
        "claim_id",
        "action",
        "correlation_id",
        "occurred_at",
    ):
        op.create_index(f"ix_task_activities_{column}", "task_activities", [column])
    op.create_index(
        "ix_task_activities_org_task_occurred",
        "task_activities",
        ["organization_id", "task_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("task_activities")
    op.drop_table("user_task_skills")
    op.drop_table("task_notifications")
    op.drop_table("tasks")
    task_status.drop(op.get_bind(), checkfirst=True)
    task_type.drop(op.get_bind(), checkfirst=True)
    task_department.drop(op.get_bind(), checkfirst=True)
