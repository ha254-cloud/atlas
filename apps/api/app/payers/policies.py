from __future__ import annotations

import hashlib
import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.payers.models import PayerPolicySource
from app.payers.repository import PayerRepository
from app.payers.schemas import PolicySourceCreate

logger = logging.getLogger(__name__)


class PayerPolicyService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = PayerRepository(db, organization_id)

    def create_version(
        self,
        payer_id: int,
        payload: PolicySourceCreate,
        *,
        actor_id: int,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> PayerPolicySource:
        self._payer(payer_id)
        policy_code = payload.policy_code.strip().upper()
        prior = [
            item
            for item in self.repository.list_policy_sources(payer_id)
            if item.policy_code == policy_code
        ]
        content = payload.content.strip()
        source = PayerPolicySource(
            organization_id=self.organization_id,
            payer_id=payer_id,
            policy_code=policy_code,
            title=payload.title.strip(),
            source_type=payload.source_type,
            jurisdiction="KE",
            version=max((item.version for item in prior), default=0) + 1,
            status="draft",
            source_reference=payload.source_reference.strip(),
            source_uri=str(payload.source_uri).strip() if payload.source_uri else None,
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            denial_categories=sorted(
                {item.strip().upper() for item in payload.denial_categories if item.strip()}
            ),
            procedure_codes=sorted(
                {item.strip().upper() for item in payload.procedure_codes if item.strip()}
            ),
            created_by=actor_id,
            change_reason=payload.reason.strip(),
        )
        self.db.add(source)
        self.db.flush()
        self._audit(
            source,
            action=AuditAction.PAYER_POLICY_CREATED,
            actor_id=actor_id,
            before=None,
            after=self._snapshot(source),
            reason=source.change_reason,
            correlation_id=correlation_id,
            ip_address=ip_address,
        )
        self.db.commit()
        self.db.refresh(source)
        return source

    def list(self, payer_id: int) -> list[PayerPolicySource]:
        self._payer(payer_id)
        return self.repository.list_policy_sources(payer_id)

    def submit_for_approval(
        self,
        payer_id: int,
        source_id: int,
        *,
        actor_id: int,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> PayerPolicySource:
        source = self._source(payer_id, source_id)
        if source.status not in {"draft", "rejected"}:
            raise ValueError(f"Policy source cannot be submitted from status '{source.status}'")
        before = self._snapshot(source)
        source.status = "pending_approval"
        source.submitted_by = actor_id
        source.submitted_at = datetime.now(UTC)
        source.rejected_by = None
        source.rejected_at = None
        source.rejection_reason = None
        return self._commit_transition(
            source,
            action=AuditAction.PAYER_POLICY_SUBMITTED,
            actor_id=actor_id,
            before=before,
            reason="Policy source submitted for approval",
            correlation_id=correlation_id,
            ip_address=ip_address,
        )

    def approve(
        self,
        payer_id: int,
        source_id: int,
        *,
        actor_id: int,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> PayerPolicySource:
        payer = self._payer(payer_id)
        source = self._source(payer_id, source_id)
        if payer.approval_status != "approved":
            raise ValueError("Payer configuration must be approved before its policy sources")
        if source.status != "pending_approval":
            raise ValueError(f"Policy source cannot be approved from status '{source.status}'")
        if source.submitted_by == actor_id:
            raise ValueError("A policy source cannot be approved by the same user who submitted it")
        before = self._snapshot(source)
        for prior in self.repository.list_policy_sources(payer_id):
            if (
                prior.id != source.id
                and prior.policy_code == source.policy_code
                and prior.status == "approved"
            ):
                prior.status = "retired"
        source.status = "approved"
        source.approved_by = actor_id
        source.approved_at = datetime.now(UTC)
        approved = self._commit_transition(
            source,
            action=AuditAction.PAYER_POLICY_APPROVED,
            actor_id=actor_id,
            before=before,
            reason="Policy source approved for appeal grounding",
            correlation_id=correlation_id,
            ip_address=ip_address,
        )
        logger.info(
            "Payer policy source approved organization_id=%s payer_id=%s source_id=%s version=%s",
            self.organization_id,
            payer_id,
            source_id,
            source.version,
        )
        return approved

    def reject(
        self,
        payer_id: int,
        source_id: int,
        *,
        reason: str,
        actor_id: int,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> PayerPolicySource:
        source = self._source(payer_id, source_id)
        if source.status != "pending_approval":
            raise ValueError(f"Policy source cannot be rejected from status '{source.status}'")
        if source.submitted_by == actor_id:
            raise ValueError("A policy source cannot be rejected by the same user who submitted it")
        before = self._snapshot(source)
        source.status = "rejected"
        source.rejected_by = actor_id
        source.rejected_at = datetime.now(UTC)
        source.rejection_reason = reason.strip()
        return self._commit_transition(
            source,
            action=AuditAction.PAYER_POLICY_REJECTED,
            actor_id=actor_id,
            before=before,
            reason=reason,
            correlation_id=correlation_id,
            ip_address=ip_address,
        )

    def applicable(
        self,
        payer_id: int,
        *,
        on_date: date,
        denial_category: str | None,
        procedure_codes: set[str],
    ) -> list[PayerPolicySource]:
        latest: dict[str, PayerPolicySource] = {}
        normalized_category = (denial_category or "").upper()
        normalized_procedures = {item.upper() for item in procedure_codes}
        for source in self.repository.approved_policy_sources(payer_id, on_date=on_date):
            if source.policy_code in latest:
                continue
            if source.denial_categories and normalized_category not in source.denial_categories:
                continue
            if source.procedure_codes and normalized_procedures.isdisjoint(source.procedure_codes):
                continue
            latest[source.policy_code] = source
        return list(latest.values())

    def _payer(self, payer_id: int):
        payer = self.repository.get(payer_id)
        if payer is None:
            raise ValueError("Payer not found")
        return payer

    def _source(self, payer_id: int, source_id: int) -> PayerPolicySource:
        source = self.repository.get_policy_source(payer_id, source_id)
        if source is None:
            raise ValueError("Policy source not found")
        return source

    def _commit_transition(
        self,
        source: PayerPolicySource,
        *,
        action: AuditAction,
        actor_id: int,
        before: dict[str, Any],
        reason: str,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> PayerPolicySource:
        self._audit(
            source,
            action=action,
            actor_id=actor_id,
            before=before,
            after=self._snapshot(source),
            reason=reason,
            correlation_id=correlation_id,
            ip_address=ip_address,
        )
        self.db.commit()
        self.db.refresh(source)
        return source

    def _audit(
        self,
        source: PayerPolicySource,
        *,
        action: AuditAction,
        actor_id: int,
        before: dict[str, Any] | None,
        after: dict[str, Any],
        reason: str,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> None:
        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=action,
            entity="payer_policy_source",
            entity_id=source.id,
            ip_address=ip_address,
            metadata={
                "before": before,
                "after": after,
                "reason": reason.strip(),
                "correlation_id": correlation_id,
            },
        )

    @staticmethod
    def _snapshot(source: PayerPolicySource) -> dict[str, Any]:
        return {
            "payer_id": source.payer_id,
            "policy_code": source.policy_code,
            "version": source.version,
            "status": source.status,
            "jurisdiction": source.jurisdiction,
            "source_type": source.source_type,
            "source_reference": source.source_reference,
            "content_sha256": source.content_sha256,
            "effective_from": source.effective_from.isoformat(),
            "effective_to": source.effective_to.isoformat() if source.effective_to else None,
        }
