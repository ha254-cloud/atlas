"""
NotificationHandler — subscribes to APPEAL_APPROVED and CLAIM_ANALYZED and
emails the analyst assigned to the claim (Claim.assigned_user_id), if one
is set.

APPEAL_APPROVED is the concrete "Appeal Approved -> Notification Service
decides how to notify" example from the Sprint 8 spec. CLAIM_ANALYZED
(Sprint 11) lets the assigned analyst know a claim is ready to review the
moment AI analysis completes, instead of only finding out by refreshing
the dashboard. Only email is wired for now (the existing, real
`EmailService` — SMS/push/Teams/Slack have no vendor integration anywhere
in this codebase yet, so they're deliberately not faked here). Real-time
dashboard notification for the same events is handled separately by
`DashboardHandler` (subscribed to every event, not just these).

Opens its own short-lived DB session (same pattern as
app/workers/tasks.py) since handlers run outside any request/task's
session scope.
"""

import logging

logger = logging.getLogger(__name__)


class NotificationHandler:
    def __call__(self, event_type: str, payload: dict, organization_id: int | None) -> None:
        claim_id = payload.get("claim_id")
        if claim_id is None:
            return

        from app.db.database import get_db
        from app.events.event_types import EventType
        from app.models.claim import Claim
        from app.models.user import User
        from app.services.email_service import EmailService

        db = next(get_db())
        try:
            claim = db.query(Claim).filter(Claim.id == claim_id).first()
            if claim is None or claim.assigned_user_id is None:
                return
            user = db.query(User).filter(User.id == claim.assigned_user_id).first()
            if user is None or not user.email:
                return

            if event_type == EventType.CLAIM_ANALYZED:
                subject = f"AI analysis ready — claim {claim.claim_number}"
                body = (
                    f"AI analysis has completed for claim {claim.claim_number}. "
                    "Review the recommended action in your recovery workspace."
                )
            elif event_type == EventType.APPEAL_GENERATED:
                subject = f"Appeal draft ready — claim {claim.claim_number}"
                body = (
                    f"An AI appeal draft is ready for claim {claim.claim_number}. "
                    "Review and edit the draft before approval."
                )
            else:
                subject = f"Appeal approved — claim {claim.claim_number}"
                body = (
                    f"The appeal for claim {claim.claim_number} has been approved "
                    "and is ready to submit to the payer."
                )

            EmailService().send_custom(to=user.email, subject=subject, body=body)
        except Exception:
            logger.exception(
                "NotificationHandler failed to process %s for claim %s", event_type, claim_id
            )
        finally:
            db.close()
