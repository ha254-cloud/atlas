"""Add enterprise organization profile and versioned tenant settings.

Revision ID: f7a2c9d4e6b1
Revises: e4b8c2d6f1a9
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f7a2c9d4e6b1"
down_revision: str | Sequence[str] | None = "e4b8c2d6f1a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("timezone", sa.String(64), nullable=True))
    op.add_column("organizations", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("success_fee_percentage", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column("organizations", sa.Column("billing_email", sa.String(255), nullable=True))
    op.add_column(
        "organizations",
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE organizations AS organization
        SET timezone = 'UTC',
            currency = COALESCE(
                NULLIF((
                    SELECT schedule.currency
                    FROM recovery_fee_schedules AS schedule
                    WHERE schedule.organization_id = organization.id
                    ORDER BY schedule.effective_from DESC, schedule.id DESC
                    LIMIT 1
                ), 'XXX'),
                'USD'
            ),
            success_fee_percentage = COALESCE((
                SELECT schedule.fee_percentage
                FROM recovery_fee_schedules AS schedule
                WHERE schedule.organization_id = organization.id
                ORDER BY schedule.effective_from DESC, schedule.id DESC
                LIMIT 1
            ), 0),
            billing_email = organization.email
        """
    )
    op.execute(
        """
        UPDATE organizations
        SET settings = jsonb_build_object(
            'ai', jsonb_build_object(
                'provider', 'openai', 'model', 'gpt-5',
                'temperature', 0.2, 'prompt_version', 'v1'
            ),
            'workflow', jsonb_build_object(
                'auto_analyze', false, 'auto_appeal', false,
                'require_approval', true
            ),
            'submission', jsonb_build_object(
                'connector', null, 'retry_count', 3,
                'polling_interval_seconds', 300
            ),
            'billing', jsonb_build_object(
                'success_fee_percentage', success_fee_percentage,
                'currency', currency, 'vat_percentage', 0,
                'payment_terms_days', 30,
                'invoice_frequency', 'monthly'
            ),
            'branding', jsonb_build_object(
                'logo_document_id', null, 'letterhead_document_id', null,
                'signature_document_id', null, 'primary_color', '#174A5C'
            ),
            'features', jsonb_build_object(
                'ai_analysis', true, 'ai_appeal', true,
                'payment_tracking', true, 'analytics', true,
                'copilot', true, 'portal_automation', false
            )
        )
        """
    )
    for column, type_ in (
        ("timezone", sa.String(64)),
        ("currency", sa.String(3)),
        ("success_fee_percentage", sa.Numeric(5, 2)),
        ("settings", postgresql.JSONB(astext_type=sa.Text())),
    ):
        op.alter_column("organizations", column, existing_type=type_, nullable=False)

    op.drop_constraint(
        "uq_recovery_fee_schedules_org_effective_from",
        "recovery_fee_schedules",
        type_="unique",
    )

    op.create_table(
        "organization_settings_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "version",
            name="uq_organization_settings_versions_org_version",
        ),
    )
    op.create_index(
        "ix_organization_settings_versions_organization_id",
        "organization_settings_versions",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_settings_versions_correlation_id",
        "organization_settings_versions",
        ["correlation_id"],
    )


def downgrade() -> None:
    duplicates = op.get_bind().execute(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT organization_id, effective_from
                FROM recovery_fee_schedules
                GROUP BY organization_id, effective_from
                HAVING count(*) > 1
            ) AS duplicate_dates
            """
        )
    ).scalar_one()
    if duplicates:
        raise RuntimeError(
            "Cannot restore one-fee-schedule-per-day constraint while "
            "same-day amendments exist"
        )
    op.create_unique_constraint(
        "uq_recovery_fee_schedules_org_effective_from",
        "recovery_fee_schedules",
        ["organization_id", "effective_from"],
    )
    op.drop_index(
        "ix_organization_settings_versions_correlation_id",
        table_name="organization_settings_versions",
    )
    op.drop_index(
        "ix_organization_settings_versions_organization_id",
        table_name="organization_settings_versions",
    )
    op.drop_table("organization_settings_versions")
    for column in (
        "settings",
        "billing_email",
        "success_fee_percentage",
        "currency",
        "timezone",
    ):
        op.drop_column("organizations", column)