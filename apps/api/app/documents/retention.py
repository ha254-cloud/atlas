from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.documents import storage
from app.documents.schemas import DocumentRetentionDecision, DocumentRetentionRun
from app.governance.models import RetentionEnforcementMode, RetentionPolicy
from app.models.document import (
    Document,
    DocumentHold,
    DocumentHoldType,
    DocumentRetentionStatus,
)


class RetentionPolicyNotFound(ValueError):
    pass


class RetentionEnforcementDenied(ValueError):
    pass


class RetentionDocumentNotFound(ValueError):
    pass


class RetentionStorageFailure(RuntimeError):
    pass


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class DocumentRetentionService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.audit = AuditService(db)

    def record_hold(
        self,
        document_id: int,
        hold_type: DocumentHoldType,
        active: bool,
        reason: str,
        actor_id: int,
        correlation_id: str,
    ) -> DocumentHold:
        document = self._document(document_id)
        previous = (
            self.db.query(DocumentHold)
            .filter(
                DocumentHold.organization_id == self.organization_id,
                DocumentHold.document_id == document.id,
                DocumentHold.hold_type == hold_type,
            )
            .order_by(DocumentHold.version.desc())
            .first()
        )
        hold = DocumentHold(
            organization_id=self.organization_id,
            document_id=document.id,
            hold_type=hold_type,
            version=(previous.version + 1) if previous else 1,
            active=active,
            reason=reason,
            recorded_by_id=actor_id,
            correlation_id=correlation_id,
            created_at=datetime.now(UTC),
        )
        self.db.add(hold)
        self.db.flush()
        self.audit.log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.DOCUMENT_HOLD_RECORDED,
            entity="document_hold",
            entity_id=hold.id,
            correlation_id=correlation_id,
            reason=reason,
            before_state={"active": previous.active, "version": previous.version}
            if previous
            else None,
            after_state={
                "document_id": document.id,
                "hold_type": hold_type.value,
                "active": active,
                "version": hold.version,
            },
        )
        self.db.commit()
        self.db.refresh(hold)
        return hold

    def list_holds(self, document_id: int) -> list[DocumentHold]:
        self._document(document_id)
        return (
            self.db.query(DocumentHold)
            .filter(
                DocumentHold.organization_id == self.organization_id,
                DocumentHold.document_id == document_id,
            )
            .order_by(DocumentHold.hold_type, DocumentHold.version.desc())
            .all()
        )

    def dry_run(
        self,
        actor_id: int,
        correlation_id: str,
        as_of: datetime | None = None,
    ) -> DocumentRetentionRun:
        run = self._evaluate(as_of)
        self.audit.log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.DOCUMENT_RETENTION_DRY_RUN,
            entity="retention_policy",
            correlation_id=correlation_id,
            after_state={
                "policy_version": run.policy_version,
                "as_of": run.as_of.isoformat(),
                "decision_count": len(run.decisions),
            },
        )
        self.db.commit()
        return run

    def enforce(
        self,
        *,
        actor_id: int,
        correlation_id: str,
        expected_policy_version: int,
        confirm: bool,
        reason: str,
        as_of: datetime | None = None,
    ) -> DocumentRetentionRun:
        if not confirm:
            raise RetentionEnforcementDenied("Retention enforcement requires confirmation")
        run = self._evaluate(as_of)
        if run.policy_version != expected_policy_version:
            raise RetentionEnforcementDenied("Retention policy version changed; run preview again")
        if run.enforcement_mode != RetentionEnforcementMode.ENFORCE.value:
            raise RetentionEnforcementDenied("The active retention policy is report-only")

        for decision in run.decisions:
            if decision.action == "archive":
                document = self._document(decision.document_id)
                document.retention_status = DocumentRetentionStatus.ARCHIVED
                document.archived_at = run.as_of
                self._audit_enforcement(document, decision, actor_id, correlation_id, reason)
            elif decision.action == "delete":
                self._delete_document(
                    decision,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    reason=reason,
                    deleted_at=run.as_of,
                )
        self.db.commit()
        return run

    def _evaluate(self, as_of: datetime | None) -> DocumentRetentionRun:
        policy = self._policy()
        evaluated_at = _utc(as_of or datetime.now(UTC))
        documents = (
            self.db.query(Document)
            .filter(Document.organization_id == self.organization_id)
            .order_by(Document.id)
            .all()
        )
        decisions = [self._decision(document, policy, evaluated_at) for document in documents]
        return DocumentRetentionRun(
            policy_version=policy.version,
            enforcement_mode=policy.enforcement_mode,
            as_of=evaluated_at,
            decisions=decisions,
        )

    def _decision(
        self,
        document: Document,
        policy: RetentionPolicy,
        as_of: datetime,
    ) -> DocumentRetentionDecision:
        expires_at = _utc(document.created_at) + timedelta(days=policy.retention_days)
        active_holds = self.active_holds(document.id)
        if policy.legal_hold_default:
            action, reason = "hold", "active policy-default legal hold"
        elif active_holds:
            names = ", ".join(sorted(hold.value for hold in active_holds))
            action, reason = "hold", f"active {names} hold"
        elif document.retention_status == DocumentRetentionStatus.ARCHIVED:
            action, reason = "retain", "document already archived"
        elif document.retention_status == DocumentRetentionStatus.DELETED:
            action, reason = "retain", "document deletion already completed"
        elif as_of < expires_at:
            action, reason = "retain", "retention period has not expired"
        else:
            action, reason = policy.disposition, "retention period expired"
        return DocumentRetentionDecision(
            document_id=document.id,
            action=action,
            reason=reason,
            policy_version=policy.version,
            expires_at=expires_at,
        )

    def active_holds(self, document_id: int) -> set[DocumentHoldType]:
        active: set[DocumentHoldType] = set()
        for hold_type in DocumentHoldType:
            latest = (
                self.db.query(DocumentHold)
                .filter(
                    DocumentHold.organization_id == self.organization_id,
                    DocumentHold.document_id == document_id,
                    DocumentHold.hold_type == hold_type,
                )
                .order_by(DocumentHold.version.desc())
                .first()
            )
            if latest is not None and latest.active:
                active.add(hold_type)
        return active

    def _delete_document(
        self,
        decision: DocumentRetentionDecision,
        *,
        actor_id: int,
        correlation_id: str,
        reason: str,
        deleted_at: datetime,
    ) -> None:
        document = self._document(decision.document_id)
        document.retention_status = DocumentRetentionStatus.PENDING_DELETE
        self.db.commit()
        paths = {version.storage_path for version in document.versions} | {document.storage_path}
        try:
            for path in paths:
                storage.delete_file(path)
        except Exception as exc:
            self.audit.log(
                organization_id=self.organization_id,
                user_id=actor_id,
                action=AuditAction.DOCUMENT_RETENTION_FAILED,
                entity="document",
                entity_id=document.id,
                correlation_id=correlation_id,
                reason=reason,
                after_state={
                    "action": "delete",
                    "policy_version": decision.policy_version,
                    "retention_status": DocumentRetentionStatus.PENDING_DELETE.value,
                    "error_type": type(exc).__name__,
                },
            )
            self.db.commit()
            raise RetentionStorageFailure(
                "Document deletion is pending because storage cleanup failed"
            ) from exc
        document.retention_status = DocumentRetentionStatus.DELETED
        document.deleted_at = deleted_at
        document.extracted_text = None
        document.ai_summary = None
        self._audit_enforcement(document, decision, actor_id, correlation_id, reason)

    def _audit_enforcement(
        self,
        document: Document,
        decision: DocumentRetentionDecision,
        actor_id: int,
        correlation_id: str,
        reason: str,
    ) -> None:
        self.audit.log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.DOCUMENT_RETENTION_ENFORCED,
            entity="document",
            entity_id=document.id,
            correlation_id=correlation_id,
            reason=reason,
            after_state={
                "action": decision.action,
                "policy_version": decision.policy_version,
                "retention_status": document.retention_status.value,
            },
        )

    def _policy(self) -> RetentionPolicy:
        policy = (
            self.db.query(RetentionPolicy)
            .filter(
                RetentionPolicy.organization_id == self.organization_id,
                RetentionPolicy.resource_type == "documents",
            )
            .order_by(RetentionPolicy.version.desc())
            .first()
        )
        if policy is None:
            raise RetentionPolicyNotFound("No document retention policy is configured")
        return policy

    def _document(self, document_id: int) -> Document:
        document = (
            self.db.query(Document)
            .filter(
                Document.id == document_id,
                Document.organization_id == self.organization_id,
            )
            .first()
        )
        if document is None:
            raise RetentionDocumentNotFound("Document not found")
        return document
