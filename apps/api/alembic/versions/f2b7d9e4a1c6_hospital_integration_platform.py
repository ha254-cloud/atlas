"""Add hospital integration mapping and sync history.

Revision ID: f2b7d9e4a1c6
Revises: c1e6a9d4f2b7
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2b7d9e4a1c6"
down_revision: str | None = "c1e6a9d4f2b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_mapping_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_format", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "version", name="uq_integration_mapping_profiles_integration_version"),
    )
    op.create_index("ix_integration_mapping_profiles_organization_id", "integration_mapping_profiles", ["organization_id"])
    op.create_index("ix_integration_mapping_profiles_integration_id", "integration_mapping_profiles", ["integration_id"])
    op.create_index("ix_integration_mapping_profiles_correlation_id", "integration_mapping_profiles", ["correlation_id"])

    op.create_table(
        "integration_mapping_fields",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("source_field", sa.String(length=200), nullable=False),
        sa.Column("target_field", sa.String(length=100), nullable=False),
        sa.Column("transform", sa.JSON(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("default_value", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["integration_mapping_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "target_field", name="uq_integration_mapping_fields_profile_target"),
    )
    op.create_index("ix_integration_mapping_fields_profile_id", "integration_mapping_fields", ["profile_id"])

    op.create_table(
        "integration_sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("mapping_profile_id", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("records_received", sa.Integer(), nullable=False),
        sa.Column("records_imported", sa.Integer(), nullable=False),
        sa.Column("records_rejected", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("initiated_by", sa.Integer(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["initiated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.ForeignKeyConstraint(["mapping_profile_id"], ["integration_mapping_profiles.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "integration_id", "status", "correlation_id"):
        op.create_index(f"ix_integration_sync_runs_{column}", "integration_sync_runs", [column])

    op.create_table(
        "integration_sync_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("source_field", sa.String(length=200), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["sync_run_id"], ["integration_sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_sync_errors_sync_run_id", "integration_sync_errors", ["sync_run_id"])
    op.create_index("ix_integration_sync_errors_error_code", "integration_sync_errors", ["error_code"])


def downgrade() -> None:
    op.drop_table("integration_sync_errors")
    op.drop_table("integration_sync_runs")
    op.drop_table("integration_mapping_fields")
    op.drop_table("integration_mapping_profiles")
