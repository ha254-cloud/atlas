from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.recovery_case import RecoveryCase, RecoveryStatus


class DashboardService:
    """
    Aggregates key metrics for the executive dashboard.
    All queries are scoped by organization_id — no cross-tenant data leaks.
    """

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def get_summary(self) -> dict:
        total_claims = self._count_claims()
        denied_claims = self._count_denied_claims()
        recovery_opportunities = self._count_open_recovery_cases()
        estimated_recovery = self._sum_estimated_recovery()
        high_priority = self._count_high_priority()

        return {
            "claims": total_claims,
            "denied_claims": denied_claims,
            "recovery_opportunities": recovery_opportunities,
            "estimated_recovery": float(estimated_recovery),
            "high_priority": high_priority,
        }

    def _count_claims(self) -> int:
        return (
            self.db.query(func.count(Claim.id))
            .filter(Claim.organization_id == self.organization_id)
            .scalar()
            or 0
        )

    def _count_denied_claims(self) -> int:
        return (
            self.db.query(func.count(Claim.id))
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.status == "denied",
            )
            .scalar()
            or 0
        )

    def _count_open_recovery_cases(self) -> int:
        return (
            self.db.query(func.count(RecoveryCase.id))
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status == RecoveryStatus.OPEN,
            )
            .scalar()
            or 0
        )

    def _sum_estimated_recovery(self) -> Decimal:
        result = (
            self.db.query(func.sum(RecoveryCase.estimated_value))
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status.in_([RecoveryStatus.OPEN, RecoveryStatus.IN_PROGRESS]),
            )
            .scalar()
        )
        return result or Decimal("0")

    def _count_high_priority(self) -> int:
        high_score_threshold = Decimal("70")
        return (
            self.db.query(func.count(RecoveryCase.id))
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status == RecoveryStatus.OPEN,
                RecoveryCase.recovery_score >= high_score_threshold,
            )
            .scalar()
            or 0
        )
