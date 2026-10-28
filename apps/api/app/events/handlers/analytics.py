"""
AnalyticsHandler — subscribes to PAYMENT_RECEIVED and refreshes that payer's
PayerStatistics row (see app/decisions/payer_stats_service.py, built in
Sprint 6) so payer performance numbers stay current without anyone
remembering to call a refresh endpoint after every payment.

Deliberately narrow: PayerStatisticsService already computes every number
from real persisted data (never guessed) — this handler's only job is
calling `refresh_payer()` for the right payer at the right time, replacing
what would otherwise require a manual/periodic refresh.
"""

import logging

logger = logging.getLogger(__name__)


class AnalyticsHandler:
    def __call__(self, event_type: str, payload: dict, organization_id: int | None) -> None:
        claim_id = payload.get("claim_id")
        if claim_id is None or organization_id is None:
            return

        from app.db.database import get_db
        from app.decisions.payer_stats_service import PayerStatisticsService
        from app.models.claim import Claim

        db = next(get_db())
        try:
            claim = (
                db.query(Claim)
                .filter(Claim.id == claim_id, Claim.organization_id == organization_id)
                .first()
            )
            if claim is None or claim.payer_id is None:
                return
            PayerStatisticsService(db, organization_id).refresh_payer(claim.payer_id)
        except Exception:
            logger.exception(
                "AnalyticsHandler failed to refresh payer stats for claim %s", claim_id
            )
        finally:
            db.close()
