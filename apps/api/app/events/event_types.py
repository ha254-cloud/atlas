from enum import Enum


class EventType(str, Enum):
    CLAIM_IMPORTED = "claim.imported"

    CLAIM_ANALYZED = "claim.analyzed"

    DENIAL_FOUND = "claim.denial_found"

    RECOVERY_CREATED = "recovery.created"

    APPEAL_GENERATED = "appeal.generated"

    BILLING_POSTED = "billing.posted"

    PAYMENT_POSTED = "payment.posted"

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

    CLAIMS_SYNCED = "claims.synced"

    SYNC_FAILED = "sync.failed"

    INTEGRATION_CONNECTED = "integration.connected"

    INTEGRATION_DISCONNECTED = "integration.disconnected"

    WORKFLOW_TRANSITIONED = "workflow.transitioned"

    WORKFLOW_ESCALATED = "workflow.escalated"

    # Added for Sprint 8 (Event Bus & Automation Engine) — fill out the
    # vocabulary the spec asked for. Only add values here that don't already
    # exist above under a different name (e.g. CLAIM_ANALYZED/APPEAL_GENERATED
    # already covered claim.analyzed/appeal.generated, so they're not
    # duplicated).
    CLAIM_CREATED = "claim.created"

    CLAIM_UPDATED = "claim.updated"

    CLAIM_FAILED = "claim.failed"

    CLAIM_SUBMITTED = "claim.submitted"

    CLAIM_ADJUDICATION_RECEIVED = "claim.adjudication_received"

    CLAIM_SUBMISSION_FAILED = "claim.submission_failed"

    CLAIM_ADJUDICATION_CHECK_FAILED = "claim.adjudication_check_failed"

    DOCUMENT_UPLOADED = "document.uploaded"

    DOCUMENT_PROCESSED = "document.processed"

    APPEAL_APPROVED = "appeal.approved"

    APPEAL_SUBMITTED = "appeal.submitted"

    APPEAL_SUBMISSION_UPDATED = "appeal.submission_updated"

    SUBMISSION_CREATED = "submission.created"

    SUBMISSION_SUBMITTED = "submission.submitted"

    SUBMISSION_ACKNOWLEDGED = "submission.acknowledged"

    SUBMISSION_FAILED = "submission.failed"

    SUBMISSION_PAID = "submission.paid"

    APPEAL_FOLLOW_UP_DUE = "appeal.follow_up_due"

    PAYMENT_RECEIVED = "payment.received"

    PAYMENT_VERIFIED = "payment.verified"

    INVOICE_GENERATED = "invoice.generated"

    WORKFLOW_STARTED = "workflow.started"

    WORKFLOW_COMPLETED = "workflow.completed"

    USER_CREATED = "user.created"

    ORGANIZATION_CREATED = "organization.created"

    PATIENT_CREATED = "patient.created"

    PATIENT_UPDATED = "patient.updated"

    TASK_CREATED = "task.created"

    TASK_ASSIGNED = "task.assigned"

    TASK_COMPLETED = "task.completed"

    TASK_OVERDUE = "task.overdue"

    TASK_ESCALATED = "task.escalated"
