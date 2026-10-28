from decimal import Decimal

from sqlalchemy import extract, func, or_
from sqlalchemy.orm import Session

from app.models.appeal import Appeal, AppealStatus
from app.models.claim import Claim
from app.models.claim_analysis import AnalysisStatus, ClaimAnalysis
from app.models.import_job import ImportJob
from app.models.recovery_case import AIReviewDecision, RecoveryCase, RecoveryStatus


class DashboardRepository:
    """
    Read-only aggregate queries for the dashboard.
    Every query is scoped by organization_id — no cross-tenant data.
    No business logic lives here.
    """

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def get_claim_count(self) -> int:
        return (
            self.db.query(func.count(Claim.id))
            .filter(Claim.organization_id == self.organization_id)
            .scalar()
            or 0
        )

    def get_denial_count(self) -> int:
        return (
            self.db.query(func.count(Claim.id))
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.status == "denied",
            )
            .scalar()
            or 0
        )

    def get_open_recovery_count(self) -> int:
        return (
            self.db.query(func.count(RecoveryCase.id))
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status == RecoveryStatus.OPEN,
            )
            .scalar()
            or 0
        )

    def get_estimated_recovery_total(self) -> Decimal:
        result = (
            self.db.query(func.sum(RecoveryCase.estimated_value))
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status.in_([RecoveryStatus.OPEN, RecoveryStatus.IN_PROGRESS]),
            )
            .scalar()
        )
        return result or Decimal("0")

    def get_high_priority_count(self, threshold: Decimal = Decimal("70")) -> int:
        return (
            self.db.query(func.count(RecoveryCase.id))
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status == RecoveryStatus.OPEN,
                RecoveryCase.recovery_score >= threshold,
            )
            .scalar()
            or 0
        )

    def get_paid_amount_total(self) -> Decimal:
        result = (
            self.db.query(func.sum(Claim.paid_amount))
            .filter(Claim.organization_id == self.organization_id)
            .scalar()
        )
        return result or Decimal("0")

    def get_billed_amount_total(self) -> Decimal:
        result = (
            self.db.query(func.sum(Claim.billed_amount))
            .filter(Claim.organization_id == self.organization_id)
            .scalar()
        )
        return result or Decimal("0")

    def get_ai_success_rate(self) -> float:
        """Percentage of AI recommendations that were accepted by specialists."""
        total = (
            self.db.query(func.count(RecoveryCase.id))
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.ai_review.isnot(None),
            )
            .scalar()
            or 0
        )
        if total == 0:
            return 0.0
        accepted = (
            self.db.query(func.count(RecoveryCase.id))
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.ai_review == AIReviewDecision.ACCEPTED,
            )
            .scalar()
            or 0
        )
        return round(accepted / total * 100, 1)

    def get_appeals_pending(self) -> int:
        return (
            self.db.query(func.count(Appeal.id))
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.status == AppealStatus.SUBMITTED,
            )
            .scalar()
            or 0
        )

    def get_claims_requiring_attention(self) -> int:
        """Denied + pending claims that have no open recovery case."""
        return (
            self.db.query(func.count(Claim.id))
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.status.in_(["denied", "pending"]),
            )
            .scalar()
            or 0
        )

    def get_analyzed_count(self) -> int:
        """Claims that have a completed AI analysis."""
        return (
            self.db.query(func.count(ClaimAnalysis.id))
            .filter(
                ClaimAnalysis.organization_id == self.organization_id,
                ClaimAnalysis.analysis_status == AnalysisStatus.COMPLETED,
            )
            .scalar()
            or 0
        )

    def get_pending_analysis_count(self) -> int:
        """Claims still waiting on AI analysis — either no ClaimAnalysis row
        exists yet (analysis not dispatched/finished) or one exists but is
        still PENDING."""
        return (
            self.db.query(func.count(Claim.id))
            .outerjoin(ClaimAnalysis, ClaimAnalysis.claim_id == Claim.id)
            .filter(
                Claim.organization_id == self.organization_id,
                or_(
                    ClaimAnalysis.id.is_(None),
                    ClaimAnalysis.analysis_status == AnalysisStatus.PENDING,
                ),
            )
            .scalar()
            or 0
        )

    def get_recent_claims(self, limit: int = 5) -> list:
        return (
            self.db.query(Claim)
            .filter(Claim.organization_id == self.organization_id)
            .order_by(Claim.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_recent_imports(self, limit: int = 5) -> list:
        return (
            self.db.query(ImportJob)
            .filter(ImportJob.organization_id == self.organization_id)
            .order_by(ImportJob.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_monthly_trend(self, months: int = 7) -> list[dict]:
        """Return month-by-month claim and recovery totals."""
        rows = (
            self.db.query(
                extract("year", Claim.created_at).label("year"),
                extract("month", Claim.created_at).label("month"),
                func.count(Claim.id).label("claims"),
                func.sum(Claim.paid_amount).label("recovered"),
            )
            .filter(Claim.organization_id == self.organization_id)
            .group_by("year", "month")
            .order_by("year", "month")
            .limit(months)
            .all()
        )
        return [
            {
                "month": f"{int(r.year)}-{int(r.month):02d}",
                "claims": int(r.claims),
                "recovered": float(r.recovered or 0),
            }
            for r in rows
        ]
