from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.ai.cost_tracking import ai_call_context
from app.ai.exceptions import AIProviderError
from app.ai.gateway import gateway
from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.claims.repository import ClaimRepository
from app.claims.timeline import ClaimTimeline
from app.documents import extraction, storage
from app.documents.repository import DocumentRepository
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.claim_event import ClaimEventType
from app.models.document import (
    Document,
    DocumentClassificationReviewStatus,
    DocumentType,
)


class DocumentNotFound(ValueError):
    pass


class DuplicateDocument(ValueError):
    pass


class DocumentAIUnavailable(RuntimeError):
    pass


class DocumentService:
    """Evidence Library — upload/list/tag/delete/summarize supporting
    documents attached to a claim (operative reports, imaging, referrals,
    lab results, authorizations)."""

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.claim_repo = ClaimRepository(db, organization_id)
        self.document_repo = DocumentRepository(db, organization_id)
        self.timeline = ClaimTimeline(db)
        self.audit = AuditService(db)
        self.events = EventPublisher()

    def _get_claim(self, claim_id: int):
        claim = self.claim_repo.get(claim_id)
        if claim is None:
            raise DocumentNotFound(f"Claim {claim_id} not found")
        return claim

    def upload(
        self, claim_id: int, file, document_type: DocumentType, uploaded_by_id: int | None
    ) -> Document:
        claim = self._get_claim(claim_id)

        storage_path, file_size, checksum = storage.save_upload(file, self.organization_id)
        if self.document_repo.get_by_claim_checksum(claim.id, checksum) is not None:
            storage.delete_file(storage_path)
            raise DuplicateDocument("This file is already attached to the claim")
        extraction_result = extraction.extract_document(storage_path, file.content_type or "")

        document = Document(
            organization_id=self.organization_id,
            claim_id=claim.id,
            uploaded_by_id=uploaded_by_id,
            document_type=document_type,
            filename=file.filename,
            storage_path=storage_path,
            content_type=file.content_type or "application/octet-stream",
            file_size=file_size,
            checksum=checksum,
            tags=[],
            extracted_text=extraction_result.text,
            extraction_status=extraction_result.status,
            extraction_method=extraction_result.method,
            extraction_engine=extraction_result.engine,
            extraction_engine_version=extraction_result.engine_version,
            extraction_confidence=extraction_result.confidence,
        )
        self.document_repo.add(document)
        self.db.flush()

        self.timeline.record(
            organization_id=self.organization_id,
            claim_id=claim.id,
            event_type=ClaimEventType.DOCUMENT_UPLOADED,
            description=f"Document uploaded: {file.filename}",
            actor_id=uploaded_by_id,
            metadata={"document_id": document.id, "document_type": document_type.value},
        )
        self._audit(
            actor_id=uploaded_by_id,
            action=AuditAction.DOCUMENT_UPLOADED,
            document=document,
            before=None,
            after=self._snapshot(document),
            reason="claim evidence uploaded",
        )

        self.db.commit()
        self.db.refresh(document)
        self.events.publish(
            EventType.DOCUMENT_UPLOADED,
            {
                "claim_id": claim.id,
                "document_id": document.id,
                "document_type": document.document_type.value,
                "organization_id": self.organization_id,
            },
            self.organization_id,
        )
        return document

    def list_for_claim(self, claim_id: int, search: str | None = None) -> list[Document]:
        self._get_claim(claim_id)
        return self.document_repo.list_for_claim(claim_id, search)

    def get(self, document_id: int) -> Document:
        document = self.document_repo.get(document_id)
        if document is None:
            raise DocumentNotFound(f"Document {document_id} not found")
        return document

    def update(
        self,
        document_id: int,
        document_type: DocumentType | None,
        tags: list[str] | None,
        actor_id: int,
    ) -> Document:
        document = self.get(document_id)
        before = self._snapshot(document)
        if document_type is not None:
            document.document_type = document_type
        if tags is not None:
            document.tags = tags
        self._audit(
            actor_id=actor_id,
            action=AuditAction.DOCUMENT_UPDATED,
            document=document,
            before=before,
            after=self._snapshot(document),
            reason="document metadata updated",
        )
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document_id: int, actor_id: int) -> None:
        document = self.get(document_id)
        self._audit(
            actor_id=actor_id,
            action=AuditAction.DOCUMENT_DELETED,
            document=document,
            before=self._snapshot(document),
            after=None,
            reason="document deleted",
        )
        storage.delete_file(document.storage_path)
        self.document_repo.delete(document)
        self.db.commit()

    async def summarize(self, document_id: int, actor_id: int) -> Document:
        """Generate an AI summary of the document's extracted text. Best-
        effort: if there's no extracted text (unsupported format, or OCR
        unavailable for a scanned image) this raises so the caller can
        surface a clear reason instead of silently returning nothing."""
        document = self.get(document_id)
        if not document.extracted_text:
            raise ValueError(
                "No extracted text available for this document — it may be a "
                "scanned image (OCR isn't configured) or an unsupported format."
            )

        with ai_call_context(organization_id=self.organization_id, claim_id=document.claim_id):
            summary = await gateway.generate(
                task="documentation",
                prompt=document.extracted_text[:8000],
                system=(
                    "Summarize this claim-supporting document in 2-4 sentences for a "
                    "revenue-cycle analyst. Focus on facts relevant to a denial appeal: "
                    "what the document proves, dates, and any missing/ambiguous details."
                ),
            )
        document.ai_summary = summary
        self._audit(
            actor_id=actor_id,
            action=AuditAction.DOCUMENT_SUMMARIZED,
            document=document,
            before={"ai_summary": None},
            after={"ai_summary": summary},
            reason="AI summary requested",
        )
        self.db.commit()
        self.db.refresh(document)
        return document

    async def classify(self, document_id: int, actor_id: int) -> Document:
        document = self.get(document_id)
        if not document.extracted_text:
            raise ValueError("Document classification requires extracted text")

        try:
            with ai_call_context(organization_id=self.organization_id, claim_id=document.claim_id):
                result = await gateway.generate_json(
                    task="document_classification",
                    prompt=document.extracted_text[:8000],
                    system=(
                        "Classify this healthcare claim document. Return JSON with "
                        "document_type and confidence. document_type must be one of: "
                        + ", ".join(item.value for item in DocumentType)
                        + ". confidence must be between 0 and 1. Do not infer facts "
                        "that are absent from the text."
                    ),
                )
        except AIProviderError as exc:
            raise DocumentAIUnavailable("Document classification provider is unavailable") from exc

        predicted_type, confidence = self._validate_classification(result)
        before = self._classification_snapshot(document)
        document.predicted_document_type = predicted_type
        document.classification_confidence = confidence
        document.classification_provider = gateway.provider_name_for("document_classification")
        document.classification_model = gateway.model_for("document_classification")
        document.classification_prompt_version = gateway.prompt_version_for(
            "document_classification"
        )
        document.classification_review_status = DocumentClassificationReviewStatus.PENDING
        document.classification_reviewed_by_id = None
        document.classification_reviewed_at = None
        document.classification_review_reason = None
        self._audit(
            actor_id=actor_id,
            action=AuditAction.DOCUMENT_CLASSIFIED,
            document=document,
            before=before,
            after=self._classification_snapshot(document),
            reason="document classification requested",
        )
        self.db.commit()
        self.db.refresh(document)
        return document

    def review_classification(
        self,
        document_id: int,
        document_type: DocumentType,
        reason: str,
        actor_id: int,
    ) -> Document:
        document = self.get(document_id)
        if document.predicted_document_type is None:
            raise ValueError("Document must be classified before review")

        before = self._classification_snapshot(document)
        status = (
            DocumentClassificationReviewStatus.ACCEPTED
            if document_type == document.predicted_document_type
            else DocumentClassificationReviewStatus.CORRECTED
        )
        document.document_type = document_type
        document.classification_review_status = status
        document.classification_reviewed_by_id = actor_id
        document.classification_reviewed_at = datetime.now(UTC)
        document.classification_review_reason = reason
        self._audit(
            actor_id=actor_id,
            action=AuditAction.DOCUMENT_CLASSIFICATION_REVIEWED,
            document=document,
            before=before,
            after=self._classification_snapshot(document),
            reason=reason,
        )
        self.db.commit()
        self.db.refresh(document)
        return document

    @staticmethod
    def _validate_classification(result: dict) -> tuple[DocumentType, Decimal]:
        if not isinstance(result, dict) or "error" in result:
            raise DocumentAIUnavailable("Document classification provider returned no result")
        try:
            predicted_type = DocumentType(result["document_type"])
            confidence = Decimal(str(result["confidence"]))
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            raise DocumentAIUnavailable(
                "Document classification provider returned invalid data"
            ) from exc
        if not Decimal("0") <= confidence <= Decimal("1"):
            raise DocumentAIUnavailable("Document classification confidence is out of range")
        return predicted_type, confidence

    @staticmethod
    def _classification_snapshot(document: Document) -> dict:
        return {
            "predicted_document_type": document.predicted_document_type.value
            if document.predicted_document_type
            else None,
            "classification_confidence": float(document.classification_confidence)
            if document.classification_confidence is not None
            else None,
            "classification_provider": document.classification_provider,
            "classification_model": document.classification_model,
            "classification_prompt_version": document.classification_prompt_version,
            "classification_review_status": document.classification_review_status.value
            if document.classification_review_status
            else None,
            "classification_reviewed_by_id": document.classification_reviewed_by_id,
            "classification_reviewed_at": document.classification_reviewed_at.isoformat()
            if document.classification_reviewed_at
            else None,
            "classification_review_reason": document.classification_review_reason,
        }

    @staticmethod
    def _snapshot(document: Document) -> dict:
        return {
            "claim_id": document.claim_id,
            "document_type": document.document_type.value,
            "filename": document.filename,
            "file_size": document.file_size,
            "checksum": document.checksum,
            "tags": list(document.tags),
        }

    def _audit(
        self,
        *,
        actor_id: int | None,
        action: AuditAction,
        document: Document,
        before: dict | None,
        after: dict | None,
        reason: str,
    ) -> None:
        if actor_id is None:
            return
        self.audit.log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=action,
            entity="document",
            entity_id=document.id,
            reason=reason,
            before_state=before,
            after_state=after,
            metadata={
                "claim_id": document.claim_id,
                "before": before,
                "after": after,
                "reason": reason,
            },
        )
