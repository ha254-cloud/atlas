"""Add payment, recovery fee schedule, and auditable billing fields.

Revision ID: e4b8c2d6f1a9
Revises: d1a5c9e3f7b2
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e4b8c2d6f1a9"
down_revision: str | Sequence[str] | None = "d1a5c9e3f7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    payment_source = postgresql.ENUM(
        "ERA_835", "API", "SFTP", "MANUAL", "WEBHOOK", name="paymentsource"
    )
    payment_status = postgresql.ENUM(
        "PENDING", "PARTIAL", "PAID", "DENIED", "VOIDED", "REVERSED",
        name="paymentstatus",
    )
    payment_source.create(op.get_bind(), checkfirst=True)
    payment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("appeal_submissions.id"), nullable=True),
        sa.Column("payer_name", sa.String(255), nullable=False),
        sa.Column("payment_reference", sa.String(255), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("adjustment_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("status", postgresql.ENUM(name="paymentstatus", create_type=False), nullable=False),
        sa.Column("source", postgresql.ENUM(name="paymentsource", create_type=False), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "organization_id", "source", "payment_reference",
            name="uq_payments_org_source_reference",
        ),
    )
    for column in ("organization_id", "claim_id", "submission_id", "payment_date", "status", "source", "correlation_id"):
        op.create_index(f"ix_payments_{column}", "payments", [column])

    op.create_table(
        "recovery_fee_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("fee_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("vat_percentage", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "organization_id", "effective_from",
            name="uq_recovery_fee_schedules_org_effective_from",
        ),
    )
    op.create_index("ix_recovery_fee_schedules_organization_id", "recovery_fee_schedules", ["organization_id"])
    op.create_index("ix_recovery_fee_schedules_effective_from", "recovery_fee_schedules", ["effective_from"])
    op.execute(
        """
        INSERT INTO recovery_fee_schedules
            (organization_id, fee_percentage, vat_percentage, currency, payment_terms_days,
             effective_from, reason, created_at, updated_at)
        SELECT id, 5.00, 0.00, 'XXX', 30, DATE '1970-01-01',
               'Migrated historical Atlas recovery fee', now(), now()
        FROM organizations
        """
    )

    op.add_column("recoveries", sa.Column("payment_id", sa.Integer(), nullable=True))
    op.add_column("recoveries", sa.Column("recovery_percentage", sa.Numeric(7, 2), nullable=True))
    op.add_column("recoveries", sa.Column("verified_by", sa.Integer(), nullable=True))
    op.add_column("recoveries", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recoveries", sa.Column("verification_reason", sa.String(500), nullable=True))
    op.create_foreign_key("fk_recoveries_payment_id_payments", "recoveries", "payments", ["payment_id"], ["id"])
    op.create_foreign_key("fk_recoveries_verified_by_users", "recoveries", "users", ["verified_by"], ["id"])
    op.create_index("ix_recoveries_payment_id", "recoveries", ["payment_id"], unique=True)
    op.alter_column("recoveries", "submission_id", existing_type=sa.Integer(), nullable=True)

    op.execute(
        """
        INSERT INTO payments
            (organization_id, claim_id, submission_id, payer_name,
             payment_reference, payment_date, expected_amount, paid_amount,
             adjustment_amount, currency, payment_method, status, source,
             raw_payload, matched_at, correlation_id, created_at, updated_at)
        SELECT recovery.organization_id, recovery.claim_id, recovery.submission_id,
               payer.name, 'legacy-recovery-' || recovery.id,
               recovery.payment_date, recovery.expected_amount,
               recovery.paid_amount, 0, 'XXX', 'unknown',
               'PAID'::paymentstatus, 'MANUAL'::paymentsource,
               jsonb_build_object('migration', 'e4b8c2d6f1a9', 'recovery_id', recovery.id),
               recovery.created_at, 'legacy-' || recovery.id,
               recovery.created_at, recovery.updated_at
        FROM recoveries AS recovery
        JOIN claims AS claim ON claim.id = recovery.claim_id
        JOIN payers AS payer ON payer.id = claim.payer_id
        """
    )
    op.execute(
        """
        UPDATE recoveries AS recovery
        SET payment_id = payment.id,
            recovery_percentage = CASE
                WHEN recovery.expected_amount > 0
                THEN round((recovery.recovered_amount / recovery.expected_amount) * 100, 2)
                ELSE 0
            END
        FROM payments AS payment
        WHERE payment.organization_id = recovery.organization_id
          AND payment.payment_reference = 'legacy-recovery-' || recovery.id
        """
    )
    op.alter_column("recoveries", "payment_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("recoveries", "recovery_percentage", existing_type=sa.Numeric(7, 2), nullable=False)

    op.add_column("invoices", sa.Column("vat_percentage", sa.Numeric(5, 2), nullable=True))
    op.add_column("invoices", sa.Column("vat_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("invoices", sa.Column("total_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("invoices", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column("invoices", sa.Column("payment_terms_days", sa.Integer(), nullable=True))
    op.add_column("invoices", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("billing_name", sa.String(255), nullable=True))
    op.add_column("invoices", sa.Column("billing_email", sa.String(255), nullable=True))
    op.add_column("invoices", sa.Column("pdf_path", sa.String(500), nullable=True))
    op.add_column("invoices", sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE invoices AS invoice
        SET vat_percentage = 0, vat_amount = 0,
            total_amount = total_fee_amount, currency = 'XXX',
            payment_terms_days = 30, due_date = period_end + 30,
            billing_name = organization.name,
            billing_email = organization.email
        FROM organizations AS organization
        WHERE organization.id = invoice.organization_id
        """
    )
    for column, type_ in (
        ("vat_percentage", sa.Numeric(5, 2)),
        ("vat_amount", sa.Numeric(14, 2)),
        ("total_amount", sa.Numeric(14, 2)),
        ("currency", sa.String(3)),
        ("payment_terms_days", sa.Integer()),
        ("due_date", sa.Date()),
        ("billing_name", sa.String(255)),
        ("billing_email", sa.String(255)),
    ):
        op.alter_column("invoices", column, existing_type=type_, nullable=False)

    op.add_column("invoice_lines", sa.Column("payment_id", sa.Integer(), nullable=True))
    op.add_column("invoice_lines", sa.Column("payment_date", sa.Date(), nullable=True))
    op.create_foreign_key("fk_invoice_lines_payment_id_payments", "invoice_lines", "payments", ["payment_id"], ["id"])
    op.create_index("ix_invoice_lines_payment_id", "invoice_lines", ["payment_id"])
    op.execute(
        """
        UPDATE invoice_lines AS line
        SET payment_id = recovery.payment_id,
            payment_date = recovery.payment_date
        FROM recoveries AS recovery
        WHERE recovery.id = line.recovery_id
        """
    )
    op.alter_column("invoice_lines", "payment_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("invoice_lines", "payment_date", existing_type=sa.Date(), nullable=False)


def downgrade() -> None:
    op.drop_column("invoice_lines", "payment_date")
    op.drop_constraint("fk_invoice_lines_payment_id_payments", "invoice_lines", type_="foreignkey")
    op.drop_index("ix_invoice_lines_payment_id", table_name="invoice_lines")
    op.drop_column("invoice_lines", "payment_id")
    for column in ("pdf_generated_at", "pdf_path", "billing_email", "billing_name", "due_date", "payment_terms_days", "currency", "total_amount", "vat_amount", "vat_percentage"):
        op.drop_column("invoices", column)
    op.alter_column("recoveries", "submission_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("fk_recoveries_verified_by_users", "recoveries", type_="foreignkey")
    op.drop_constraint("fk_recoveries_payment_id_payments", "recoveries", type_="foreignkey")
    op.drop_index("ix_recoveries_payment_id", table_name="recoveries")
    for column in ("verification_reason", "verified_at", "verified_by", "recovery_percentage", "payment_id"):
        op.drop_column("recoveries", column)
    op.drop_table("recovery_fee_schedules")
    op.drop_table("payments")
    postgresql.ENUM(name="paymentstatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="paymentsource").drop(op.get_bind(), checkfirst=True)
