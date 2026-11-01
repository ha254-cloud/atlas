"""
Fine-grained permission system for Atlas.

Roles (UserRole) are coarse buckets a user is assigned; Permissions are the
actual actions the API gates. ROLE_PERMISSIONS maps every role to the set of
actions it may perform. This is intentionally a plain Python mapping (not a
database table) to match the existing codebase convention of enum-driven
lookup structures (see AuditAction, ClaimEventType) rather than a dynamic
admin-editable RBAC table — that's a reasonable future upgrade if org admins
need to customize roles, but isn't needed yet.

`User.is_superuser` bypasses every permission check (see
`require_permission` in app/security/dependencies.py) — this finally gives
that previously-unused flag real meaning.
"""

from enum import StrEnum

from app.models.user import UserRole


class Permission(StrEnum):
    VIEW_BRANCHES = "view_branches"
    MANAGE_BRANCHES = "manage_branches"
    VIEW_PATIENTS = "view_patients"
    CREATE_PATIENTS = "create_patients"
    EDIT_PATIENTS = "edit_patients"
    VIEW_CLAIMS = "view_claims"
    EXPORT_CLAIMS = "export_claims"
    VIEW_CLINICAL_DOCUMENTS = "view_clinical_documents"
    EDIT_CLAIMS = "edit_claims"
    UPLOAD_CLAIMS = "upload_claims"
    SUBMIT_CLAIMS = "submit_claims"
    GENERATE_APPEALS = "generate_appeals"
    SUBMIT_APPEALS = "submit_appeals"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_USERS = "manage_users"
    CONFIGURE_INTEGRATIONS = "configure_integrations"
    APPROVE_PAYERS = "approve_payers"
    MANAGE_BILLING = "manage_billing"
    VIEW_AUDIT_LOG = "view_audit_log"
    MANAGE_WORKFLOWS = "manage_workflows"
    MANAGE_ORGANIZATION = "manage_organization"
    ACCESS_COPILOT = "access_copilot"
    COPILOT_WRITE_ACTIONS = "copilot_write_actions"
    VIEW_TASKS = "view_tasks"
    MANAGE_TASKS = "manage_tasks"
    VIEW_GOVERNANCE = "view_governance"
    MANAGE_GOVERNANCE = "manage_governance"


_ALL_PERMISSIONS: set[Permission] = set(Permission)


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    # Full access — org owner / administrator.
    UserRole.OWNER: set(_ALL_PERMISSIONS),
    UserRole.ADMIN: set(_ALL_PERMISSIONS),
    # Revenue cycle manager — everything short of billing.
    UserRole.MANAGER: {
        Permission.VIEW_BRANCHES,
        Permission.VIEW_PATIENTS,
        Permission.CREATE_PATIENTS,
        Permission.EDIT_PATIENTS,
        Permission.VIEW_CLAIMS,
        Permission.EXPORT_CLAIMS,
        Permission.EDIT_CLAIMS,
        Permission.UPLOAD_CLAIMS,
        Permission.SUBMIT_CLAIMS,
        Permission.GENERATE_APPEALS,
        Permission.SUBMIT_APPEALS,
        Permission.VIEW_ANALYTICS,
        Permission.MANAGE_USERS,
        Permission.CONFIGURE_INTEGRATIONS,
        Permission.APPROVE_PAYERS,
        Permission.VIEW_AUDIT_LOG,
        Permission.MANAGE_WORKFLOWS,
        Permission.ACCESS_COPILOT,
        Permission.COPILOT_WRITE_ACTIONS,
        Permission.VIEW_TASKS,
        Permission.MANAGE_TASKS,
        Permission.VIEW_GOVERNANCE,
    },
    # Works claims and analytics day-to-day, doesn't manage the team.
    UserRole.REVENUE_ANALYST: {
        Permission.VIEW_BRANCHES,
        Permission.VIEW_PATIENTS,
        Permission.CREATE_PATIENTS,
        Permission.EDIT_PATIENTS,
        Permission.VIEW_CLAIMS,
        Permission.VIEW_CLINICAL_DOCUMENTS,
        Permission.EDIT_CLAIMS,
        Permission.UPLOAD_CLAIMS,
        Permission.GENERATE_APPEALS,
        Permission.VIEW_ANALYTICS,
        Permission.ACCESS_COPILOT,
        Permission.VIEW_GOVERNANCE,
        Permission.VIEW_TASKS,
    },
    # Drafts and submits appeals.
    UserRole.APPEALS_SPECIALIST: {
        Permission.VIEW_BRANCHES,
        Permission.VIEW_PATIENTS,
        Permission.VIEW_CLAIMS,
        Permission.VIEW_CLINICAL_DOCUMENTS,
        Permission.EDIT_CLAIMS,
        Permission.GENERATE_APPEALS,
        Permission.SUBMIT_APPEALS,
        Permission.VIEW_ANALYTICS,
        Permission.ACCESS_COPILOT,
        Permission.VIEW_TASKS,
    },
    # Handles claim data entry/uploads and billing-adjacent work.
    UserRole.BILLER: {
        Permission.VIEW_BRANCHES,
        Permission.VIEW_PATIENTS,
        Permission.CREATE_PATIENTS,
        Permission.EDIT_PATIENTS,
        Permission.VIEW_CLAIMS,
        Permission.EDIT_CLAIMS,
        Permission.UPLOAD_CLAIMS,
        Permission.SUBMIT_CLAIMS,
        Permission.VIEW_ANALYTICS,
        Permission.ACCESS_COPILOT,
        Permission.VIEW_TASKS,
    },
    # Read-only + compliance visibility into the audit trail.
    UserRole.AUDITOR: {
        Permission.VIEW_BRANCHES,
        Permission.VIEW_PATIENTS,
        Permission.VIEW_CLAIMS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_AUDIT_LOG,
        Permission.VIEW_GOVERNANCE,
        Permission.ACCESS_COPILOT,
    },
    # Read only.
    UserRole.VIEWER: {
        Permission.VIEW_BRANCHES,
        Permission.VIEW_PATIENTS,
        Permission.VIEW_CLAIMS,
        Permission.VIEW_ANALYTICS,
        Permission.ACCESS_COPILOT,
    },
}


def role_has_permission(role: UserRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
