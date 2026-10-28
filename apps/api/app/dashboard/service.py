from decimal import Decimal

from sqlalchemy.orm import Session

from app.dashboard.repository import DashboardRepository
from app.dashboard.schemas import (
    ClaimSummary,
    DashboardMetrics,
    DashboardResponse,
    ImportSummary,
    RecoveryTrendPoint,
)


class DashboardService:
    """
    Combines repository data into the single DashboardResponse.
    One API call → one response → dashboard loads instantly.
    """

    def __init__(self, db: Session, organization_id: int):
        self.repo = DashboardRepository(db, organization_id)

    def get_dashboard(self) -> DashboardResponse:
        claims = self.repo.get_claim_count()
        denied = self.repo.get_denial_count()
        opportunities = self.repo.get_open_recovery_count()
        estimated = self.repo.get_estimated_recovery_total()
        high_priority = self.repo.get_high_priority_count()
        billed = self.repo.get_billed_amount_total()
        paid = self.repo.get_paid_amount_total()

        recovery_rate = float(paid / billed * 100) if billed > Decimal("0") else 0.0

        metrics = DashboardMetrics(
            claims=claims,
            denied_claims=denied,
            recovery_opportunities=opportunities,
            estimated_recovery=float(estimated),
            high_priority=high_priority,
            recovery_rate=round(recovery_rate, 2),
            ai_success_rate=self.repo.get_ai_success_rate(),
            appeals_pending=self.repo.get_appeals_pending(),
            claims_requiring_attention=self.repo.get_claims_requiring_attention(),
            analyzed_claims=self.repo.get_analyzed_count(),
            pending_analysis=self.repo.get_pending_analysis_count(),
        )

        recent_claims = [
            ClaimSummary(
                id=c.id,
                claim_number=c.claim_number,
                status=c.status,
                billed_amount=float(c.billed_amount),
                paid_amount=float(c.paid_amount),
                service_date=str(c.service_date) if c.service_date else None,
                created_at=c.created_at,
            )
            for c in self.repo.get_recent_claims()
        ]

        recent_imports = [
            ImportSummary(
                id=j.id,
                source=j.source,
                status=j.status,
                total_records=j.total_records,
                successful_records=j.successful_records,
                failed_records=j.failed_records,
                created_at=j.created_at,
            )
            for j in self.repo.get_recent_imports()
        ]

        trend_raw = self.repo.get_monthly_trend()
        recovery_trend = [
            RecoveryTrendPoint(
                month=r["month"],
                claims=r["claims"],
                recovered=0,
                estimated_value=r["recovered"],
            )
            for r in trend_raw
        ]

        return DashboardResponse(
            metrics=metrics,
            recent_claims=recent_claims,
            recent_imports=recent_imports,
            recovery_trend=recovery_trend,
        )
