"""Add revenue safety attribution ledgers.

Revision ID: b5d9e2f7c1a4
Revises: a6c8e2f4b9d1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b5d9e2f7c1a4"
down_revision: str | None = "a6c8e2f4b9d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _immutable_trigger(table_name: str) -> None:
    function_name = f"prevent_{table_name}_mutation"
    trigger_name = f"{table_name}_immutable"
    op.execute(f"""
        CREATE FUNCTION {function_name}() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'revenue attribution ledgers are immutable';
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
        "recovery_fee_schedules",
        sa.Column("dispute_period_days", sa.Integer(), server_default="0", nullable=False),
    )

    op.create_table(
        "recovery_interventions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=True),
        sa.Column("intervention_type", sa.String(50), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["appeal_submissions.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "submission_id",
            "intervention_type",
            name="uq_recovery_interventions_submission_type",
        ),
    )
    for column in ("organization_id", "claim_id", "submission_id", "intervention_type", "occurred_at", "correlation_id"):
        op.create_index(f"ix_recovery_interventions_{column}", "recovery_interventions", [column])

    op.create_table(
        "recovery_attribution_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("recovery_id", sa.Integer(), nullable=False),
        sa.Column("intervention_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("evidence_state", sa.String(30), nullable=False),
        sa.Column("confirmed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("excluded_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reversal_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("eligible_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("fee_schedule_id", sa.Integer(), nullable=False),
        sa.Column("fee_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("vat_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("dispute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["recovery_id"], ["recoveries.id"]),
        sa.ForeignKeyConstraint(["intervention_id"], ["recovery_interventions.id"]),
        sa.ForeignKeyConstraint(["fee_schedule_id"], ["recovery_fee_schedules.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recovery_id",
            "version",
            name="uq_recovery_attribution_versions_recovery_version",
        ),
    )
    for column in ("organization_id", "recovery_id", "intervention_id", "status", "correlation_id"):
        op.create_index(
            f"ix_recovery_attribution_versions_{column}",
            "recovery_attribution_versions",
            [column],
        )

    op.add_column(
        "invoice_lines",
        sa.Column("attribution_version_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_invoice_lines_attribution_version_id",
        "invoice_lines",
        "recovery_attribution_versions",
        ["attribution_version_id"],
        ["id"],
    )
    op.create_index(
        "ix_invoice_lines_attribution_version_id",
        "invoice_lines",
        ["attribution_version_id"],
        unique=True,
    )

    _immutable_trigger("recovery_interventions")
    _immutable_trigger("recovery_attribution_versions")


def downgrade() -> None:
    for table_name in ("recovery_attribution_versions", "recovery_interventions"):
        op.execute(f"DROP TRIGGER IF EXISTS {table_name}_immutable ON {table_name}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table_name}_mutation()")
    op.drop_index("ix_invoice_lines_attribution_version_id", table_name="invoice_lines")
    op.drop_constraint(
        "fk_invoice_lines_attribution_version_id",
        "invoice_lines",
        type_="foreignkey",
    )
    op.drop_column("invoice_lines", "attribution_version_id")
    op.drop_table("recovery_attribution_versions")
    op.drop_table("recovery_interventions")
    op.drop_column("recovery_fee_schedules", "dispute_period_days")
