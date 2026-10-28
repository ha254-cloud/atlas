"""Add tenant-scoped payer intelligence records.

Revision ID: b9d4e7f2a6c1
Revises: f6b2d8a4c1e9
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9d4e7f2a6c1"
down_revision: str | Sequence[str] | None = "f6b2d8a4c1e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "payer_profile_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("payer_id", sa.Integer(), sa.ForeignKey("payers.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("preferred_documents", sa.JSON(), nullable=False),
        sa.Column("contact_emails", sa.JSON(), nullable=False),
        sa.Column("escalation_contacts", sa.JSON(), nullable=False),
        sa.Column("sla_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("change_reason", sa.String(length=500), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("payer_id", "version", name="uq_payer_profile_version"),
    )
    op.create_index("ix_payer_profile_versions_organization_id", "payer_profile_versions", ["organization_id"])
    op.create_index("ix_payer_profile_versions_payer_id", "payer_profile_versions", ["payer_id"])

    op.create_table(
        "payer_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("payer_id", sa.Integer(), sa.ForeignKey("payers.id"), nullable=False),
        sa.Column("contract_code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="KES", nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("change_reason", sa.String(length=500), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "organization_id", "payer_id", "contract_code", "version", name="uq_payer_contract_version"
        ),
    )
    op.create_index("ix_payer_contracts_organization_id", "payer_contracts", ["organization_id"])
    op.create_index("ix_payer_contracts_payer_id", "payer_contracts", ["payer_id"])

    op.create_table(
        "payer_contract_tariffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("payer_contracts.id"), nullable=False),
        sa.Column("procedure_code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("contract_id", "procedure_code", name="uq_contract_tariff_procedure"),
    )
    op.create_index("ix_payer_contract_tariffs_contract_id", "payer_contract_tariffs", ["contract_id"])

    op.create_table(
        "payer_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("payer_id", sa.Integer(), sa.ForeignKey("payers.id"), nullable=False),
        sa.Column("rule_code", sa.String(length=100), nullable=False),
        sa.Column("rule_type", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("requirement", sa.String(length=30), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("change_reason", sa.String(length=500), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "organization_id", "payer_id", "rule_code", "version", name="uq_payer_rule_version"
        ),
    )
    op.create_index("ix_payer_rules_organization_id", "payer_rules", ["organization_id"])
    op.create_index("ix_payer_rules_payer_id", "payer_rules", ["payer_id"])
    op.create_index("ix_payer_rules_rule_type", "payer_rules", ["rule_type"])


def downgrade() -> None:
    op.drop_index("ix_payer_rules_rule_type", table_name="payer_rules")
    op.drop_index("ix_payer_rules_payer_id", table_name="payer_rules")
    op.drop_index("ix_payer_rules_organization_id", table_name="payer_rules")
    op.drop_table("payer_rules")
    op.drop_index("ix_payer_contract_tariffs_contract_id", table_name="payer_contract_tariffs")
    op.drop_table("payer_contract_tariffs")
    op.drop_index("ix_payer_contracts_payer_id", table_name="payer_contracts")
    op.drop_index("ix_payer_contracts_organization_id", table_name="payer_contracts")
    op.drop_table("payer_contracts")
    op.drop_index("ix_payer_profile_versions_payer_id", table_name="payer_profile_versions")
    op.drop_index("ix_payer_profile_versions_organization_id", table_name="payer_profile_versions")
    op.drop_table("payer_profile_versions")
