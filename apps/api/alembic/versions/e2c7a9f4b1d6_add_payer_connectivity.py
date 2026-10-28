"""Add payer connectivity submission records.

Revision ID: e2c7a9f4b1d6
Revises: d7b3f5a1c8e2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e2c7a9f4b1d6"
down_revision: Union[str, None] = "d7b3f5a1c8e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


submission_status = postgresql.ENUM(
    "PENDING",
    "SUBMITTING",
    "SUBMITTED",
    "ACKNOWLEDGED",
    "UNDER_REVIEW",
    "ADDITIONAL_INFO_REQUIRED",
    "ACCEPTED",
    "REJECTED",
    "DENIED",
    "PAID",
    "FAILED",
    name="appealsubmissionstatus",
)

submission_status_ref = postgresql.ENUM(
    name="appealsubmissionstatus",
    create_type=False,
)


def upgrade() -> None:
    submission_status.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TYPE claimeventtype ADD VALUE IF NOT EXISTS 'APPEAL_STATUS_UPDATED'")
    op.create_table(
        "appeal_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("appeal_id", sa.Integer(), sa.ForeignKey("appeals.id"), nullable=False),
        sa.Column("integration_id", sa.Integer(), sa.ForeignKey("integrations.id"), nullable=True),
        sa.Column("connector", sa.String(50), nullable=False),
        sa.Column("external_tracking_id", sa.String(255), nullable=True),
        sa.Column("status", submission_status_ref, nullable=False, server_default="PENDING"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("appeal_id", name="uq_appeal_submissions_appeal_id"),
    )
    op.create_index("ix_appeal_submissions_organization_id", "appeal_submissions", ["organization_id"])
    op.create_index("ix_appeal_submissions_appeal_id", "appeal_submissions", ["appeal_id"])
    op.create_index("ix_appeal_submissions_integration_id", "appeal_submissions", ["integration_id"])
    op.create_index("ix_appeal_submissions_connector", "appeal_submissions", ["connector"])
    op.create_index("ix_appeal_submissions_external_tracking_id", "appeal_submissions", ["external_tracking_id"])
    op.create_index("ix_appeal_submissions_status", "appeal_submissions", ["status"])
    op.create_index("ix_appeal_submissions_next_follow_up_at", "appeal_submissions", ["next_follow_up_at"])

    op.create_table(
        "appeal_submission_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("appeal_submissions.id"), nullable=False),
        sa.Column("status", submission_status_ref, nullable=False),
        sa.Column("message", sa.String(1000), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_appeal_submission_events_organization_id", "appeal_submission_events", ["organization_id"])
    op.create_index("ix_appeal_submission_events_submission_id", "appeal_submission_events", ["submission_id"])
    op.create_index("ix_appeal_submission_events_status", "appeal_submission_events", ["status"])
    op.create_index("ix_appeal_submission_events_occurred_at", "appeal_submission_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("appeal_submission_events")
    op.drop_table("appeal_submissions")
    submission_status.drop(op.get_bind(), checkfirst=True)