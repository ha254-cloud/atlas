import builtins

from sqlalchemy.orm import Session, joinedload

from app.core.repository import BaseRepository
from app.models.claim import Claim
from app.models.patient import Patient
from app.models.payer import Payer


class ClaimRepository(BaseRepository):
    def __init__(
        self,
        db: Session,
        organization_id: int,
        accessible_branch_ids: list[int] | None = None,
    ):
        super().__init__(db, organization_id)
        self.accessible_branch_ids = accessible_branch_ids

    def _base_query(self):
        """All claim queries must be scoped to the current organization."""
        query = (
            self.db.query(Claim)
            .options(
                joinedload(Claim.patient),
                joinedload(Claim.payer),
                joinedload(Claim.assigned_user),
                joinedload(Claim.denials),
                joinedload(Claim.recovery_cases),
                joinedload(Claim.claim_lines),
                joinedload(Claim.diagnoses),
                joinedload(Claim.documents),
                joinedload(Claim.analysis),
                joinedload(Claim.organization),
            )
            .filter(Claim.organization_id == self.organization_id)
        )
        if self.accessible_branch_ids is not None:
            query = query.filter(Claim.branch_id.in_(self.accessible_branch_ids))
        return query

    def create(self, claim: Claim) -> Claim:
        self.db.add(claim)
        return claim

    def get(self, claim_id: int) -> Claim | None:
        return self._base_query().filter(Claim.id == claim_id).first()

    def update(self, claim_id: int, **fields) -> Claim | None:
        claim = self.get(claim_id)
        if not claim:
            return None
        for k, v in fields.items():
            setattr(claim, k, v)
        return claim

    def delete(self, claim_id: int) -> bool:
        claim = self.get(claim_id)
        if not claim:
            return False
        self.db.delete(claim)
        return True

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        status: str | None = None,
        payer_id: int | None = None,
        priority: str | None = None,
        assigned_user_id: int | None = None,
        min_risk_score: float | None = None,
    ) -> list[Claim]:
        query = self._base_query()
        if search:
            query = self._apply_search(query, search)
        if status:
            query = query.filter(Claim.status == status)
        if payer_id:
            query = query.filter(Claim.payer_id == payer_id)
        if priority:
            query = query.filter(Claim.priority == priority)
        if assigned_user_id:
            query = query.filter(Claim.assigned_user_id == assigned_user_id)
        if min_risk_score is not None:
            query = query.filter(Claim.ai_risk_score >= min_risk_score)
        return query.order_by(Claim.created_at.desc()).offset(offset).limit(limit).all()

    def search(self, q: str) -> builtins.list[Claim]:
        return self._apply_search(self._base_query(), q).all()

    def _apply_search(self, query, q: str):
        like = f"%{q}%"
        return (
            query.outerjoin(Patient, Claim.patient_id == Patient.id)
            .outerjoin(Payer, Claim.payer_id == Payer.id)
            .filter(
                Claim.claim_number.ilike(like)
                | Patient.first_name.ilike(like)
                | Patient.last_name.ilike(like)
                | Payer.name.ilike(like)
            )
        )

    def get_by_claim_number(self, claim_number: str) -> Claim | None:
        return self._base_query().filter(Claim.claim_number == claim_number).first()
