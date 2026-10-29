"""Add payment settlement, allocation, and credit-note ledgers.

Revision ID: 7c2e8a4f9b1d
Revises: 14d669265fc7
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7c2e8a4f9b1d"
down_revision: str | Sequence[str] | None = "14d669265fc7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _immutable_trigger(table_name: str, message: str) -> None:
    function_name = f"prevent_{table_name}_mutation"
    trigger_name = f"{table_name}_immutable"
    op.execute(f"""
        CREATE FUNCTION {function_name}() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '{message}';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(f"""
        CREATE TRIGGER {trigger_name}
        BEFORE UPDATE OR DELETE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION {function_name}()
    """)
    op.execute(f"ALTER TABLE {table_name} ENABLE ALWAYS TRIGGER {trigger_name}")


def upgrade() -> None:
    op.create_table(
        "payment_settlement_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column("settlement_reference", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_payment_settlement_evidence_org_idempotency",
        ),
    )
    for column in (
        "organization_id",
        "payment_id",
        "evidence_type",
        "received_at",
        "correlation_id",
    ):
        op.create_index(
            f"ix_payment_settlement_evidence_{column}",
            "payment_settlement_evidence",
            [column],
        )

    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=True),
        sa.Column("parent_allocation_id", sa.Integer(), nullable=True),
        sa.Column("allocation_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column(
            "actor_type",
            sa.String(length=20),
            server_default="system",
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["parent_allocation_id"],
            ["payment_allocations.id"],
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["appeal_submissions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_payment_allocations_org_idempotency",
        ),
    )
    for column in (
        "organization_id",
        "payment_id",
        "claim_id",
        "submission_id",
        "parent_allocation_id",
        "allocation_type",
        "correlation_id",
    ):
        op.create_index(
            f"ix_payment_allocations_{column}",
            "payment_allocations",
            [column],
        )

    op.create_table(
        "invoice_credit_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("invoice_line_id", sa.Integer(), nullable=False),
        sa.Column("payment_allocation_id", sa.Integer(), nullable=False),
        sa.Column("credit_note_number", sa.String(length=50), nullable=False),
        sa.Column("adjustment_type", sa.String(length=20), nullable=False),
        sa.Column(
            "recovered_adjustment_amount",
            sa.Numeric(14, 2),
            nullable=False,
        ),
        sa.Column("fee_adjustment_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("vat_adjustment_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_credit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("issued_by", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["invoice_line_id"], ["invoice_lines.id"]),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["payment_allocation_id"],
            ["payment_allocations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "credit_note_number",
            name="uq_invoice_credit_notes_org_number",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "payment_allocation_id",
            name="uq_invoice_credit_notes_org_allocation",
        ),
    )
    for column in (
        "organization_id",
        "invoice_id",
        "invoice_line_id",
        "payment_allocation_id",
        "correlation_id",
    ):
        op.create_index(
            f"ix_invoice_credit_notes_{column}",
            "invoice_credit_notes",
            [column],
        )

    op.execute("""
        INSERT INTO payment_settlement_evidence (
            organization_id, payment_id, evidence_type, settlement_reference,
            amount, currency, received_at, source_hash, actor_id, reason,
            correlation_id, idempotency_key
        )
        SELECT
            organization_id, id, 'migrated_payment', payment_reference,
            paid_amount, currency, created_at,
            encode(sha256(convert_to(raw_payload::text, 'UTF8')), 'hex'),
            matched_by_id, 'Backfilled from canonical payment evidence',
            correlation_id, 'migrated-payment-' || id
        FROM payments
    """)
    op.execute("""
        INSERT INTO payment_allocations (
            organization_id, payment_id, claim_id, submission_id,
            allocation_type, amount, currency, actor_id, actor_type, reason,
            correlation_id, idempotency_key, item_index
        )
        SELECT
            recovery.organization_id, recovery.payment_id, recovery.claim_id,
            recovery.submission_id, 'allocation', recovery.recovered_amount,
            payment.currency, recovery.verified_by,
            CASE WHEN recovery.verified_by IS NULL THEN 'system' ELSE 'user' END,
            'Backfilled from canonical recovery evidence',
            payment.correlation_id, 'migrated-recovery-' || recovery.id, 0
        FROM recoveries AS recovery
        JOIN payments AS payment ON payment.id = recovery.payment_id
    """)

    op.drop_index("ix_recoveries_payment_id", table_name="recoveries")
    op.create_index(
        "ix_recoveries_payment_id",
        "recoveries",
        ["payment_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_recoveries_payment_claim",
        "recoveries",
        ["payment_id", "claim_id"],
    )

    _immutable_trigger(
        "payment_settlement_evidence",
        "payment settlement evidence is immutable",
    )
    _immutable_trigger("payment_allocations", "payment allocations are immutable")
    _immutable_trigger("invoice_credit_notes", "invoice credit notes are immutable")


def downgrade() -> None:
    duplicate_payment = op.get_bind().execute(sa.text("""
        SELECT payment_id
        FROM recoveries
        GROUP BY payment_id
        HAVING count(*) > 1
        LIMIT 1
    """)).scalar_one_or_none()
    if duplicate_payment is not None:
        raise RuntimeError(
            "Cannot restore one-recovery-per-payment while split allocations exist"
        )

    for table_name in (
        "invoice_credit_notes",
        "payment_allocations",
        "payment_settlement_evidence",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {table_name}_immutable ON {table_name}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table_name}_mutation()")

    op.drop_constraint(
        "uq_recoveries_payment_claim",
        "recoveries",
        type_="unique",
    )
    op.drop_index("ix_recoveries_payment_id", table_name="recoveries")
    op.create_index(
        "ix_recoveries_payment_id",
        "recoveries",
        ["payment_id"],
        unique=True,
    )
    op.drop_table("invoice_credit_notes")
    op.drop_table("payment_allocations")
    op.drop_table("payment_settlement_evidence")
