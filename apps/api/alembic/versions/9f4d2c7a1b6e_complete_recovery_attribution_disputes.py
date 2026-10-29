"""Complete recovery attribution, disputes, and invoice reconciliation.

Revision ID: 9f4d2c7a1b6e
Revises: 7c2e8a4f9b1d
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9f4d2c7a1b6e"
down_revision: str | Sequence[str] | None = "7c2e8a4f9b1d"
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
    op.add_column(
        "recovery_attribution_versions",
        sa.Column("previous_version_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_recovery_attribution_versions_previous_version_id",
        "recovery_attribution_versions",
        "recovery_attribution_versions",
        ["previous_version_id"],
        ["id"],
    )
    op.create_index(
        "ix_recovery_attribution_versions_previous_version_id",
        "recovery_attribution_versions",
        ["previous_version_id"],
    )

    op.create_table(
        "recovery_attribution_disputes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("recovery_id", sa.Integer(), nullable=False),
        sa.Column("attribution_version_id", sa.Integer(), nullable=False),
        sa.Column("opened_by", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["attribution_version_id"], ["recovery_attribution_versions.id"]),
        sa.ForeignKeyConstraint(["opened_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["recovery_id"], ["recoveries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attribution_version_id",
            name="uq_recovery_attribution_disputes_version",
        ),
    )
    for column in (
        "organization_id",
        "recovery_id",
        "attribution_version_id",
        "correlation_id",
    ):
        op.create_index(
            f"ix_recovery_attribution_disputes_{column}",
            "recovery_attribution_disputes",
            [column],
        )

    op.create_table(
        "recovery_attribution_dispute_resolutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("dispute_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("eligible_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("resolved_by", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["dispute_id"], ["recovery_attribution_disputes.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dispute_id",
            name="uq_recovery_attribution_dispute_resolutions_dispute",
        ),
    )
    for column in ("organization_id", "dispute_id", "outcome", "correlation_id"):
        op.create_index(
            f"ix_recovery_attribution_dispute_resolutions_{column}",
            "recovery_attribution_dispute_resolutions",
            [column],
        )

    op.alter_column(
        "invoice_credit_notes",
        "payment_allocation_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "invoice_credit_notes",
        sa.Column("attribution_resolution_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_invoice_credit_notes_attribution_resolution_id",
        "invoice_credit_notes",
        "recovery_attribution_dispute_resolutions",
        ["attribution_resolution_id"],
        ["id"],
    )
    op.create_index(
        "ix_invoice_credit_notes_attribution_resolution_id",
        "invoice_credit_notes",
        ["attribution_resolution_id"],
    )
    op.create_unique_constraint(
        "uq_invoice_credit_notes_org_attribution_resolution",
        "invoice_credit_notes",
        ["organization_id", "attribution_resolution_id"],
    )
    op.create_check_constraint(
        "ck_invoice_credit_notes_single_source",
        "invoice_credit_notes",
        "(payment_allocation_id IS NOT NULL) <> "
        "(attribution_resolution_id IS NOT NULL)",
    )

    op.create_table(
        "invoice_reconciliation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_payment_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("expected_recovered_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_recovered_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("expected_fee_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_fee_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("expected_vat_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_vat_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("credit_note_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("expected_net_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_net_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discrepancy_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discrepancy_count", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("run_by", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["run_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "invoice_id", "status", "correlation_id"):
        op.create_index(
            f"ix_invoice_reconciliation_runs_{column}",
            "invoice_reconciliation_runs",
            [column],
        )

    for table_name in (
        "recovery_attribution_disputes",
        "recovery_attribution_dispute_resolutions",
        "invoice_reconciliation_runs",
    ):
        _immutable_trigger(table_name, f"{table_name} are immutable")


def downgrade() -> None:
    for table_name in (
        "invoice_reconciliation_runs",
        "recovery_attribution_dispute_resolutions",
        "recovery_attribution_disputes",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {table_name}_immutable ON {table_name}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table_name}_mutation()")

    op.drop_table("invoice_reconciliation_runs")
    op.drop_constraint(
        "ck_invoice_credit_notes_single_source",
        "invoice_credit_notes",
        type_="check",
    )
    op.drop_constraint(
        "uq_invoice_credit_notes_org_attribution_resolution",
        "invoice_credit_notes",
        type_="unique",
    )
    op.drop_index(
        "ix_invoice_credit_notes_attribution_resolution_id",
        table_name="invoice_credit_notes",
    )
    op.drop_constraint(
        "fk_invoice_credit_notes_attribution_resolution_id",
        "invoice_credit_notes",
        type_="foreignkey",
    )
    op.drop_column("invoice_credit_notes", "attribution_resolution_id")
    op.alter_column(
        "invoice_credit_notes",
        "payment_allocation_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_table("recovery_attribution_dispute_resolutions")
    op.drop_table("recovery_attribution_disputes")
    op.drop_index(
        "ix_recovery_attribution_versions_previous_version_id",
        table_name="recovery_attribution_versions",
    )
    op.drop_constraint(
        "fk_recovery_attribution_versions_previous_version_id",
        "recovery_attribution_versions",
        type_="foreignkey",
    )
    op.drop_column("recovery_attribution_versions", "previous_version_id")
