"""Submission Engine v1.

Revision ID: b8e4c2f7a1d9
Revises: fa3b5d7e9c2a
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b8e4c2f7a1d9"
down_revision: str | Sequence[str] | None = "fa3b5d7e9c2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE appealsubmissionstatus ADD VALUE IF NOT EXISTS 'IN_REVIEW'")
    op.execute("ALTER TYPE appealsubmissionstatus ADD VALUE IF NOT EXISTS 'APPROVED'")

    op.add_column(
        "appeal_submissions",
        sa.Column("claim_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "appeal_submissions",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "appeal_submissions",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_appeal_submissions_claim_id_claims",
        "appeal_submissions",
        "claims",
        ["claim_id"],
        ["id"],
    )
    op.create_index(
        "ix_appeal_submissions_claim_id",
        "appeal_submissions",
        ["claim_id"],
    )
    op.execute(
        """
        UPDATE appeal_submissions AS submission
        SET claim_id = appeal.claim_id
        FROM appeals AS appeal
        WHERE submission.appeal_id = appeal.id
          AND submission.claim_id IS NULL
        """
    )

    op.create_table(
        "recoveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("appeal_submissions.id"), nullable=False),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("recovered_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("atlas_fee_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("atlas_fee_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("submission_id", name="uq_recoveries_submission_id"),
    )
    op.create_index("ix_recoveries_organization_id", "recoveries", ["organization_id"])
    op.create_index("ix_recoveries_claim_id", "recoveries", ["claim_id"])
    op.create_index("ix_recoveries_submission_id", "recoveries", ["submission_id"])
    op.create_index("ix_recoveries_payment_date", "recoveries", ["payment_date"])
    op.create_index("ix_recoveries_verified", "recoveries", ["verified"])

    invoice_status = postgresql.ENUM(
        "DRAFT",
        "SENT",
        "PAID",
        "VOID",
        name="invoicestatus",
    )
    invoice_status.create(op.get_bind(), checkfirst=True)
    invoice_status_ref = postgresql.ENUM(name="invoicestatus", create_type=False)
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False, unique=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", invoice_status_ref, nullable=False, server_default="DRAFT"),
        sa.Column("total_recovered_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_fee_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "organization_id",
            "period_start",
            "period_end",
            name="uq_invoices_organization_period",
        ),
    )
    op.create_index("ix_invoices_organization_id", "invoices", ["organization_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("recovery_id", sa.Integer(), sa.ForeignKey("recoveries.id"), nullable=False, unique=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("recovered_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("fee_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("fee_amount", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])
    op.create_index("ix_invoice_lines_recovery_id", "invoice_lines", ["recovery_id"])
    op.create_index("ix_invoice_lines_claim_id", "invoice_lines", ["claim_id"])


def downgrade() -> None:
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    postgresql.ENUM(name="invoicestatus").drop(op.get_bind(), checkfirst=True)
    op.drop_table("recoveries")
    op.drop_index("ix_appeal_submissions_claim_id", table_name="appeal_submissions")
    op.drop_constraint(
        "fk_appeal_submissions_claim_id_claims",
        "appeal_submissions",
        type_="foreignkey",
    )
    op.drop_column("appeal_submissions", "completed_at")
    op.drop_column("appeal_submissions", "acknowledged_at")
    op.drop_column("appeal_submissions", "claim_id")
