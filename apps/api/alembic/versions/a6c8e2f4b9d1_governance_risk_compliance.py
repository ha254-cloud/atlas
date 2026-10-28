"""Add governance, risk, and compliance baseline.

Revision ID: a6c8e2f4b9d1
Revises: f2b7d9e4a1c6
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a6c8e2f4b9d1"
down_revision: str | None = "f2b7d9e4a1c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(512), nullable=True))
    op.add_column("audit_logs", sa.Column("device", sa.String(100), nullable=True))
    op.add_column("audit_logs", sa.Column("correlation_id", sa.String(100), nullable=True))
    op.add_column("audit_logs", sa.Column("reason", sa.String(500), nullable=True))
    op.add_column("audit_logs", sa.Column("before_state", sa.JSON(), nullable=True))
    op.add_column("audit_logs", sa.Column("after_state", sa.JSON(), nullable=True))
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])
    op.create_index(
        "ix_audit_logs_resource",
        "audit_logs",
        ["organization_id", "entity", "entity_id"],
    )

    op.create_table(
        "patient_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("retention_years", sa.Integer(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "patient_id", "purpose", "version",
            name="uq_patient_consents_patient_purpose_version",
        ),
    )
    op.create_index("ix_patient_consents_organization_id", "patient_consents", ["organization_id"])
    op.create_index("ix_patient_consents_patient_id", "patient_consents", ["patient_id"])
    op.create_index("ix_patient_consents_correlation_id", "patient_consents", ["correlation_id"])
    op.create_index("ix_patient_consents_org_purpose", "patient_consents", ["organization_id", "purpose"])

    op.create_table(
        "retention_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("disposition", sa.String(20), nullable=False),
        sa.Column("legal_hold_default", sa.Boolean(), nullable=False),
        sa.Column("enforcement_mode", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "resource_type", "version",
            name="uq_retention_policies_org_resource_version",
        ),
    )
    for column in ("organization_id", "resource_type", "correlation_id"):
        op.create_index(f"ix_retention_policies_{column}", "retention_policies", [column])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("device", sa.String(100), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Integer(), nullable=True),
        sa.Column("revoke_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sessions_organization_id", "user_sessions", ["organization_id"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index(
        "ix_user_sessions_org_active",
        "user_sessions",
        ["organization_id", "revoked_at", "expires_at"],
    )

    op.execute("""
        CREATE FUNCTION prevent_audit_log_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit logs are immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation()
    """)
    op.execute("ALTER TABLE audit_logs ENABLE ALWAYS TRIGGER audit_logs_immutable")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    op.drop_table("user_sessions")
    op.drop_table("retention_policies")
    op.drop_table("patient_consents")
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_correlation_id", table_name="audit_logs")
    for column in (
        "after_state", "before_state", "reason", "correlation_id", "device", "user_agent"
    ):
        op.drop_column("audit_logs", column)
