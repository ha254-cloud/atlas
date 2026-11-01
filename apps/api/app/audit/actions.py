from enum import StrEnum


class AuditAction(StrEnum):
    # Auth
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_LOGIN_FAILED = "user.login_failed"
    USER_SESSION_TERMINATED = "user.session_terminated"
    USER_REGISTER = "user.register"
    EMAIL_VERIFIED = "user.email_verified"
    PASSWORD_RESET_REQUESTED = "user.password_reset_requested"
    PASSWORD_RESET_COMPLETED = "user.password_reset_completed"
    USER_INVITED = "user.invited"
    USER_INVITE_ACCEPTED = "user.invite_accepted"

    # Organizations
    ORGANIZATION_UPDATED = "organization.updated"
    ORGANIZATION_SETTINGS_UPDATED = "organization.settings_updated"

    # Payers
    PAYER_CREATED = "payer.created"
    PAYER_UPDATED = "payer.updated"
    PAYER_SUBMITTED_FOR_APPROVAL = "payer.submitted_for_approval"
    PAYER_APPROVED = "payer.approved"
    PAYER_REJECTED = "payer.rejected"
    PAYER_POLICY_CREATED = "payer_policy.created"
    PAYER_POLICY_SUBMITTED = "payer_policy.submitted_for_approval"
    PAYER_POLICY_APPROVED = "payer_policy.approved"
    PAYER_POLICY_REJECTED = "payer_policy.rejected"

    # Claims
    CLAIM_CREATED = "claim.created"
    CLAIM_UPDATED = "claim.updated"
    CLAIM_DELETED = "claim.deleted"
    CLAIMS_EXPORTED = "claims.exported"

    # Patients
    PATIENT_CREATED = "patient.created"
    PATIENT_UPDATED = "patient.updated"

    # Branches
    BRANCH_CREATED = "branch.created"
    BRANCH_UPDATED = "branch.updated"
    DEPARTMENT_CREATED = "department.created"
    BRANCH_MEMBERSHIP_ASSIGNED = "branch_membership.assigned"

    # Documents
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_UPDATED = "document.updated"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_SUMMARIZED = "document.summarized"
    DOCUMENT_CLASSIFIED = "document.classified"
    DOCUMENT_CLASSIFICATION_REVIEWED = "document.classification_reviewed"
    DOCUMENT_HOLD_RECORDED = "document.hold_recorded"
    DOCUMENT_RETENTION_DRY_RUN = "document.retention_dry_run"
    DOCUMENT_RETENTION_FAILED = "document.retention_failed"
    DOCUMENT_RETENTION_ENFORCED = "document.retention_enforced"

    # Governance
    PATIENT_CONSENT_RECORDED = "governance.patient_consent_recorded"
    RETENTION_POLICY_VERSION_CREATED = "governance.retention_policy_version_created"

    # Platform administration
    PLATFORM_ADMIN_VIEWED = "platform_admin.viewed"

    # AI
    AI_ANALYSIS_RUN = "ai.analysis_run"
    APPEAL_GENERATED = "appeal.generated"
    APPEAL_EDITED = "appeal.edited"
    APPEAL_SUBMITTED = "appeal.submitted"

    # Payments
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_MATCHED = "payment.matched"
    PAYMENT_SETTLEMENT_EVIDENCE_RECORDED = "payment.settlement_evidence_recorded"
    PAYMENT_ALLOCATED = "payment.allocated"
    PAYMENT_ALLOCATION_ADJUSTED = "payment.allocation_adjusted"
    INVOICE_CREDIT_NOTE_ISSUED = "invoice.credit_note_issued"
    RECOVERY_VERIFIED = "recovery.verified"
    RECOVERY_INTERVENTION_RECORDED = "recovery.intervention_recorded"
    RECOVERY_ATTRIBUTION_DECIDED = "recovery.attribution_decided"
    RECOVERY_ATTRIBUTION_DISPUTED = "recovery.attribution_disputed"
    RECOVERY_ATTRIBUTION_DISPUTE_RESOLVED = "recovery.attribution_dispute_resolved"
    INVOICE_RECONCILED = "invoice.reconciled"
    RECOVERY_FEE_CONFIGURED = "recovery.fee_configured"

    # Imports
    IMPORT_STARTED = "import.started"
    IMPORT_COMPLETED = "import.completed"
    IMPORT_FAILED = "import.failed"

    # Integrations
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_CREDENTIALS_ROTATED = "integration.credentials_rotated"
    INTEGRATION_SYNC_TRIGGERED = "integration.sync_triggered"
    INTEGRATION_DISCONNECTED = "integration.disconnected"
    SHA_CLAIM_SUBMITTED = "sha_eclaim.submitted"
    SHA_CLAIM_RESPONSE_RECEIVED = "sha_eclaim.response_received"
    SHA_CLAIM_SUBMISSION_FAILED = "sha_eclaim.submission_failed"
    SHA_CLAIM_STATUS_CHECK_FAILED = "sha_eclaim.status_check_failed"

    # API keys
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"

    # Recovery Workflow Engine
    WORKFLOW_TRANSITIONED = "workflow.transitioned"
    WORKFLOW_ESCALATED = "workflow.escalated"
    WORKFLOW_DEFINITION_CREATED = "workflow.definition_created"
    WORKFLOW_DEFINITION_UPDATED = "workflow.definition_updated"
    WORKFLOW_DEFINITION_DELETED = "workflow.definition_deleted"
    WORKFLOW_APPROVAL_DECIDED = "workflow.approval_decided"

    # Revenue Recovery lifecycle
    RECOVERY_LIFECYCLE_EVENT_RECORDED = "recovery.lifecycle_event_recorded"
