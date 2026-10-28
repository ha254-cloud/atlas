from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.claim import Claim
from app.models.recovery import Recovery
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.recovery.models import RecoveryAccount, RecoveryEventType, RecoveryLifecycleEvent


def _priority_from_score(score: Decimal) -> str:
    if score >= Decimal("90"):
        return "critical"
    if score >= Decimal("70"):
        return "high"
    if score >= Decimal("40"):
        return "medium"
    return "low"


class RecoveryRepository:
    """
    Org-scoped queries for recovery cases with filtering and sorting.
    """

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def list_opportunities(
        self,
        status: str | None = None,
        payer_id: int | None = None,
        priority: str | None = None,
        search: str | None = None,
        sort_by: str = "recovery_score",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list, int]:
        query = (
            self.db.query(RecoveryCase, Claim)
            .join(Claim, RecoveryCase.claim_id == Claim.id)
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                Claim.organization_id == self.organization_id,
            )
        )

        if status:
            try:
                query = query.filter(RecoveryCase.status == RecoveryStatus(status))
            except ValueError:
                pass

        if payer_id:
            query = query.filter(Claim.payer_id == payer_id)

        if search:
            query = query.filter(Claim.claim_number.ilike(f"%{search}%"))

        if priority:
            thresholds = {
                "critical": (Decimal("90"), Decimal("100")),
                "high": (Decimal("70"), Decimal("89.99")),
                "medium": (Decimal("40"), Decimal("69.99")),
                "low": (Decimal("0"), Decimal("39.99")),
            }
            if priority in thresholds:
                lo, hi = thresholds[priority]
                query = query.filter(
                    RecoveryCase.recovery_score >= lo,
                    RecoveryCase.recovery_score <= hi,
                )

        total = query.count()

        sort_col = RecoveryCase.recovery_score
        if sort_by == "estimated_value":
            sort_col = RecoveryCase.estimated_value
        elif sort_by == "created_at":
            sort_col = RecoveryCase.created_at

        if sort_dir == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        rows = query.offset(offset).limit(limit).all()
        return rows, total

    def get_by_id(self, recovery_id: int):
        return (
            self.db.query(RecoveryCase)
            .filter(
                RecoveryCase.id == recovery_id,
                RecoveryCase.organization_id == self.organization_id,
            )
            .first()
        )

    def update_status(self, recovery_id: int, status: str) -> RecoveryCase | None:
        rc = self.get_by_id(recovery_id)
        if rc is None:
            return None
        rc.status = RecoveryStatus(status)
        self.db.commit()
        self.db.refresh(rc)
        return rc

    def get_claim(self, claim_id: int) -> Claim | None:
        return (
            self.db.query(Claim)
            .options(joinedload(Claim.payer))
            .filter(Claim.id == claim_id, Claim.organization_id == self.organization_id)
            .first()
        )

    def get_account(self, account_id: int) -> RecoveryAccount | None:
        return (
            self.db.query(RecoveryAccount)
            .filter(
                RecoveryAccount.id == account_id,
                RecoveryAccount.organization_id == self.organization_id,
            )
            .first()
        )

    def get_account_for_claim(self, claim_id: int) -> RecoveryAccount | None:
        return (
            self.db.query(RecoveryAccount)
            .filter(
                RecoveryAccount.claim_id == claim_id,
                RecoveryAccount.organization_id == self.organization_id,
            )
            .first()
        )

    def list_accounts(self) -> list[RecoveryAccount]:
        return (
            self.db.query(RecoveryAccount)
            .filter(RecoveryAccount.organization_id == self.organization_id)
            .order_by(RecoveryAccount.id)
            .all()
        )

    def events(self, account_id: int) -> list[RecoveryLifecycleEvent]:
        return (
            self.db.query(RecoveryLifecycleEvent)
            .filter(
                RecoveryLifecycleEvent.organization_id == self.organization_id,
                RecoveryLifecycleEvent.account_id == account_id,
            )
            .order_by(RecoveryLifecycleEvent.sequence)
            .all()
        )

    def event_for_idempotency(self, key: str) -> RecoveryLifecycleEvent | None:
        return (
            self.db.query(RecoveryLifecycleEvent)
            .filter(
                RecoveryLifecycleEvent.organization_id == self.organization_id,
                RecoveryLifecycleEvent.idempotency_key == key,
            )
            .first()
        )

    def next_sequence(self, account_id: int) -> int:
        latest = (
            self.db.query(func.max(RecoveryLifecycleEvent.sequence))
            .filter(
                RecoveryLifecycleEvent.organization_id == self.organization_id,
                RecoveryLifecycleEvent.account_id == account_id,
            )
            .scalar()
        )
        return int(latest or 0) + 1

    def verified_recoveries(self, claim_id: int) -> list[Recovery]:
        return (
            self.db.query(Recovery)
            .filter(
                Recovery.organization_id == self.organization_id,
                Recovery.claim_id == claim_id,
                Recovery.verified.is_(True),
            )
            .order_by(Recovery.payment_date, Recovery.id)
            .all()
        )

    def latest_case(self, claim_id: int) -> RecoveryCase | None:
        return (
            self.db.query(RecoveryCase)
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.claim_id == claim_id,
            )
            .order_by(RecoveryCase.created_at.desc(), RecoveryCase.id.desc())
            .first()
        )

    def allocation_total(self, account_id: int, event_type: RecoveryEventType) -> Decimal:
        total = (
            self.db.query(func.coalesce(func.sum(RecoveryLifecycleEvent.amount), 0))
            .filter(
                RecoveryLifecycleEvent.organization_id == self.organization_id,
                RecoveryLifecycleEvent.account_id == account_id,
                RecoveryLifecycleEvent.event_type == event_type,
            )
            .scalar()
        )
        return Decimal(total or 0)
