"""Add governed payer policy sources and appeal grounding provenance.

Revision ID: 6b8f1e3d9a2c
Revises: 4a6d8e2c0f1b
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6b8f1e3d9a2c"
down_revision: str | Sequence[str] | None = "4a6d8e2c0f1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_payers_id_org", "payers", ["id", "organization_id"])
    op.create_table(
        "payer_policy_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column("policy_code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("jurisdiction", sa.String(length=2), server_default="KE", nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("source_uri", sa.String(length=2048), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("denial_categories", sa.JSON(), nullable=False),
        sa.Column("procedure_codes", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("change_reason", sa.String(length=500), nullable=False),
        sa.Column("submitted_by", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.Integer(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["payer_id", "organization_id"],
            ["payers.id", "payers.organization_id"],
            name="fk_policy_source_payer_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "payer_id",
            "policy_code",
            "version",
            name="uq_policy_source_version",
        ),
    )
    op.create_index(
        op.f("ix_payer_policy_sources_organization_id"),
        "payer_policy_sources",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_payer_policy_sources_payer_id"),
        "payer_policy_sources",
        ["payer_id"],
    )
    op.create_index(
        op.f("ix_payer_policy_sources_policy_code"),
        "payer_policy_sources",
        ["policy_code"],
    )
    op.create_index(
        op.f("ix_payer_policy_sources_status"),
        "payer_policy_sources",
        ["status"],
    )
    op.add_column("appeals", sa.Column("grounding_report", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("appeals", "grounding_report")
    op.drop_index(op.f("ix_payer_policy_sources_status"), table_name="payer_policy_sources")
    op.drop_index(op.f("ix_payer_policy_sources_policy_code"), table_name="payer_policy_sources")
    op.drop_index(op.f("ix_payer_policy_sources_payer_id"), table_name="payer_policy_sources")
    op.drop_index(
        op.f("ix_payer_policy_sources_organization_id"),
        table_name="payer_policy_sources",
    )
    op.drop_table("payer_policy_sources")
    op.drop_constraint("uq_payers_id_org", "payers", type_="unique")
