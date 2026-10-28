from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.appeal import Appeal, AppealStatus
from app.models.appeal_version import AppealVersion
from app.models.claim import Claim
from app.models.patient import Patient
from app.models.payer import Payer


class AppealRepository:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def _base_query(self):
        return self.db.query(Appeal).filter(Appeal.organization_id == self.organization_id)

    def create(self, appeal: Appeal) -> Appeal:
        self.db.add(appeal)
        self.db.flush()
        return appeal

    def get(self, appeal_id: int) -> Appeal | None:
        return self._base_query().filter(Appeal.id == appeal_id).first()

    def list_for_claim(self, claim_id: int) -> list[Appeal]:
        return (
            self._base_query()
            .filter(Appeal.claim_id == claim_id)
            .order_by(Appeal.created_at.desc(), Appeal.id.desc())
            .all()
        )

    def latest(self, claim_id: int) -> Appeal | None:
        return (
            self._base_query()
            .filter(Appeal.claim_id == claim_id)
            .order_by(Appeal.created_at.desc(), Appeal.id.desc())
            .first()
        )

    def history(self, claim_id: int) -> list[Appeal]:
        return self.list_for_claim(claim_id)

    def list(
        self,
        *,
        status: AppealStatus | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Appeal]:
        query = (
            self._base_query()
            .join(Claim, Appeal.claim_id == Claim.id)
            .join(Payer, Claim.payer_id == Payer.id)
            .join(Patient, Claim.patient_id == Patient.id)
            .options(
                joinedload(Appeal.claim).joinedload(Claim.payer),
                joinedload(Appeal.claim).joinedload(Claim.patient),
            )
        )
        if status is not None:
            query = query.filter(Appeal.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Claim.claim_number.ilike(pattern),
                    Payer.name.ilike(pattern),
                    Patient.first_name.ilike(pattern),
                    Patient.last_name.ilike(pattern),
                )
            )
        return (
            query.order_by(Appeal.created_at.desc(), Appeal.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update(self, appeal_id: int, **fields) -> Appeal | None:
        appeal = self.get(appeal_id)
        if not appeal:
            return None
        for k, v in fields.items():
            setattr(appeal, k, v)
        self.db.flush()
        return appeal

    def approve(self, appeal_id: int, approved_by: int) -> Appeal | None:
        return self.update(
            appeal_id,
            status=AppealStatus.APPROVED,
            approved_by=approved_by,
            approved_at=datetime.now(UTC),
        )

    def delete_draft(self, appeal_id: int) -> bool:
        appeal = self.get(appeal_id)
        if appeal is None or appeal.status != AppealStatus.DRAFT:
            return False
        self.db.delete(appeal)
        self.db.flush()
        return True

    def save_generated(
        self,
        appeal_id: int,
        *,
        title: str,
        letter: str,
        confidence: float,
        required_documents: list[str],
        missing_documents: list[str],
        references: list[str],
        model: str,
    ) -> Appeal | None:
        appeal = self.get(appeal_id)
        if appeal is None or appeal.status != AppealStatus.DRAFT:
            return None

        is_placeholder = appeal.current_version == 1 and not appeal.appeal_text
        version_number = 1 if is_placeholder else appeal.current_version + 1
        if not is_placeholder:
            appeal.current_version = version_number

        appeal.title = title
        appeal.appeal_text = letter
        appeal.confidence = confidence
        appeal.required_documents = required_documents
        appeal.missing_documents = missing_documents
        appeal.references = references
        appeal.ai_provider = model
        appeal.generated_by = "ai"

        self.db.add(
            AppealVersion(
                organization_id=self.organization_id,
                appeal_id=appeal.id,
                version_number=version_number,
                appeal_text=letter,
            )
        )
        self.db.flush()
        return appeal
