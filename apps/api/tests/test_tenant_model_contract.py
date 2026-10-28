"""Schema-level guardrails for Atlas tenant ownership."""

import app.models  # noqa: F401
from app.db.database import Base

GLOBAL_TABLES = {
    "denial_codes",
    "organizations",
}

PARENT_SCOPED_TABLES = {
    "claim_diagnoses": ("claim_id", "claims.id"),
    "claim_lines": ("claim_id", "claims.id"),
    "email_verification_tokens": ("user_id", "users.id"),
    "integration_credential_versions": ("integration_id", "integrations.id"),
    "integration_mapping_fields": ("profile_id", "integration_mapping_profiles.id"),
    "integration_sync_errors": ("sync_run_id", "integration_sync_runs.id"),
    "invoice_lines": ("invoice_id", "invoices.id"),
    "password_reset_tokens": ("user_id", "users.id"),
    "webhook_delivery_logs": ("subscription_id", "webhook_subscriptions.id"),
    "workflow_step_executions": ("execution_id", "workflow_executions.id"),
    "workflow_steps": ("workflow_id", "workflow_definitions.id"),
}


def test_every_table_has_an_explicit_tenant_classification():
    tables = Base.metadata.tables
    direct_tenant_tables = {
        name for name, table in tables.items() if "organization_id" in table.c
    }

    assert set(tables) == GLOBAL_TABLES | set(PARENT_SCOPED_TABLES) | direct_tenant_tables


def test_direct_tenant_tables_require_an_organization_foreign_key():
    for table in Base.metadata.tables.values():
        if "organization_id" not in table.c:
            continue

        column = table.c.organization_id
        targets = {foreign_key.target_fullname for foreign_key in column.foreign_keys}
        assert column.nullable is False, f"{table.name}.organization_id must be NOT NULL"
        # organization_id may also participate in composite foreign keys (e.g. claims
        # enforcing that its branch_id/department_id belong to the same organization),
        # which adds extra targets such as "branches.organization_id". As long as a
        # direct reference to organizations.id is present, the column is correctly scoped.
        assert "organizations.id" in targets, (
            f"{table.name}.organization_id must reference organizations.id"
        )


def test_parent_scoped_tables_require_their_tenant_owned_parent():
    for table_name, (column_name, expected_target) in PARENT_SCOPED_TABLES.items():
        column = Base.metadata.tables[table_name].c[column_name]
        targets = {foreign_key.target_fullname for foreign_key in column.foreign_keys}
        assert column.nullable is False, f"{table_name}.{column_name} must be NOT NULL"
        assert expected_target in targets, (
            f"{table_name}.{column_name} must reference {expected_target}"
        )
