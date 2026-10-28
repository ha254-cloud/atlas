from enum import StrEnum


class WorkflowTrigger(StrEnum):
    CLAIM_CREATED = "claim.created"
    CLAIM_IMPORTED = "claim.imported"
    CLAIM_ANALYZED = "claim.analyzed"
    APPEAL_GENERATED = "appeal.generated"
    APPEAL_APPROVED = "appeal.approved"
    SUBMISSION_CREATED = "submission.created"
    SUBMISSION_FAILED = "submission.failed"
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_VERIFIED = "payment.verified"
    INVOICE_GENERATED = "invoice.generated"


SUPPORTED_WORKFLOW_TRIGGERS = frozenset(trigger.value for trigger in WorkflowTrigger)
