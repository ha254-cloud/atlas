"""
DecisionHandler — subscribes to CLAIM_ANALYZED and automatically runs the
Decision Engine (app.decisions.service.DecisionService) for the newly
analyzed claim.

Previously the Decision Engine was only ever reachable via an explicit
`POST /decisions/claims/{claim_id}/evaluate` call — nothing recomputed a
decision the moment fresh AI analysis became available, so the Decision
Queue could silently go stale. This handler closes that gap the same way
Sprint 8 wired CLAIM_IMPORTED -> AI analysis (see
app/events/handlers/claims.py): the analysis service only has to publish
CLAIM_ANALYZED, and doesn't need to know the Decision Engine exists.

Opens its own short-lived DB session (same pattern as every other handler
in this package) since handlers run outside any request/task's session
scope.
"""

import logging

logger = logging.getLogger(__name__)


class DecisionHandler:
    def __call__(self, event_type: str, payload: dict, organization_id: int | None) -> None:
        claim_id = payload.get("claim_id")
        if claim_id is None or organization_id is None:
            return

        from app.db.database import get_db
        from app.decisions.service import DecisionService

        db = next(get_db())
        try:
            DecisionService(db, organization_id).evaluate_claim(claim_id)
        except Exception:
            # Best-effort — the analysis itself already succeeded and was
            # persisted before this event fired. A missed auto-evaluation
            # can always be re-run later via the explicit API endpoint.
            logger.exception(
                "DecisionHandler failed to auto-evaluate decision for claim %s", claim_id
            )
        finally:
            db.close()
