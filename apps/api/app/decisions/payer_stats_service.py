"""
PayerStatisticsService — computes and persists PayerStatistics rows from
this organization's OWN claims/appeals/recovery-case history. Per the
product spec's explicit requirement, these numbers are never guessed or
hardcoded — every field is derived from real, already-persisted data
(the same underlying facts AnalyticsRepository.payer_performance() reads
live for the dashboard).

Deliberately a batch/on-demand REFRESH (upsert), not a live query on
every request — the Decision Engine reads PayerStatistics on every single
claim evaluation, so it needs to be cheap. Call refresh_all()/
refresh_payer() periodically (e.g. via a future Celery Beat job — none
exists yet in this codebase, see local dev notes) or on-demand via
POST /decisions/payer-statistics/refresh.
"""

from sqlalchemy.orm import Session

from app.models.appeal import Appeal, AppealStatus
from app.models.claim import Claim
from app.models.denial import Denial
from app.models.payer import Payer
from app.models.payer_statistics import PayerStatistics
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.repositories.denial_code_repository import DenialCodeRepository


class PayerStatisticsService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def refresh_all(self) -> list[PayerStatistics]:
        payers = self.db.query(Payer).filter(Payer.organization_id == self.organization_id).all()
        return [self.refresh_payer(payer.id) for payer in payers]

    def refresh_payer(self, payer_id: int) -> PayerStatistics:
        claims = (
            self.db.query(Claim)
            .filter(Claim.organization_id == self.organization_id, Claim.payer_id == payer_id)
            .all()
        )
        claim_ids = [c.id for c in claims]

        total_claims = len(claims)
        denied_claims = [c for c in claims if c.status == "denied"]
        average_denial_rate = (len(denied_claims) / total_claims * 100) if total_claims else None

        recovery_cases = (
            self.db.query(RecoveryCase).filter(RecoveryCase.claim_id.in_(claim_ids)).all()
            if claim_ids
            else []
        )
        recovered = [
            rc
            for rc in recovery_cases
            if rc.status == RecoveryStatus.RECOVERED and rc.payment_received_at and rc.created_at
        ]
        average_payment_time = None
        if recovered:
            days = [(rc.payment_received_at.date() - rc.created_at.date()).days for rc in recovered]
            average_payment_time = sum(days) / len(days)

        recovered_amounts = [
            rc.recovered_amount for rc in recovery_cases if rc.recovered_amount is not None
        ]
        average_recovery = (
            (sum(recovered_amounts) / len(recovered_amounts)) if recovered_amounts else None
        )

        appeals = (
            self.db.query(Appeal).filter(Appeal.claim_id.in_(claim_ids)).all() if claim_ids else []
        )
        terminal = [
            a
            for a in appeals
            if a.status in (AppealStatus.ACCEPTED, AppealStatus.REJECTED, AppealStatus.DENIED)
        ]
        appeal_success_rate = None
        if terminal:
            accepted = sum(1 for a in terminal if a.status == AppealStatus.ACCEPTED)
            appeal_success_rate = accepted / len(terminal) * 100

        # Documentation score: proxy for how often appeals for this payer
        # go out with NO gaps flagged by the Evidence Collector
        # (app.appeals.evidence) — a real, already-computed structural
        # signal, not a new guess.
        documentation_score = None
        if appeals:
            complete = sum(1 for a in appeals if not a.missing_documents)
            documentation_score = complete / len(appeals) * 100

        denials = (
            self.db.query(Denial)
            .filter(Denial.organization_id == self.organization_id, Denial.claim_id.in_(claim_ids))
            .all()
            if claim_ids
            else []
        )
        timely_filing_days = self._average_resolution_days(denials)

        existing = self.get(payer_id)
        if existing is None:
            existing = PayerStatistics(organization_id=self.organization_id, payer_id=payer_id)
            self.db.add(existing)

        existing.average_payment_time = average_payment_time
        existing.appeal_success_rate = appeal_success_rate
        existing.average_recovery = average_recovery
        existing.documentation_score = documentation_score
        existing.average_denial_rate = average_denial_rate
        existing.timely_filing_days = timely_filing_days
        existing.sample_size = total_claims

        self.db.commit()
        self.db.refresh(existing)
        return existing

    def _average_resolution_days(self, denials: list[Denial]) -> int | None:
        """Average typical_resolution_days (from the denial-code knowledge
        base) across this payer's actual denials — real KB data matched to
        real denials, not a guessed constant."""
        repo = DenialCodeRepository(self.db)
        resolution_days = []
        for denial in denials:
            entry = repo.get_by_code(denial.denial_code)
            if entry and entry.typical_resolution_days:
                resolution_days.append(entry.typical_resolution_days)
        if not resolution_days:
            return None
        return int(sum(resolution_days) / len(resolution_days))

    def get(self, payer_id: int) -> PayerStatistics | None:
        return (
            self.db.query(PayerStatistics)
            .filter(
                PayerStatistics.organization_id == self.organization_id,
                PayerStatistics.payer_id == payer_id,
            )
            .first()
        )
