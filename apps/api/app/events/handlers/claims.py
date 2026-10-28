"""
ClaimsHandler — subscribes to CLAIM_IMPORTED and dispatches the background
AI analysis task.

Previously `ClaimProcessor.process_canonical()` called
`analyze_claim_task.delay(...)` directly (see app/processing/processor.py's
old `_dispatch_ai()`), then separately published CLAIM_IMPORTED. That's
exactly the tight coupling the Sprint 8 spec calls out: the import pipeline
had to know AI analysis exists at all. Now the pipeline only publishes
CLAIM_IMPORTED; this handler (registered independently, see
app/events/handlers/__init__.py) decides to kick off analysis. Adding a
second, third, fourth consumer of "a claim was imported" from here on
requires zero changes to the import pipeline.
"""

import logging

logger = logging.getLogger(__name__)


class ClaimsHandler:
    def __call__(self, event_type: str, payload: dict, organization_id: int | None) -> None:
        claim_id = payload.get("claim_id")
        if claim_id is None or organization_id is None:
            return
        try:
            from app.workers.tasks import analyze_claim_task

            analyze_claim_task.delay(claim_id, organization_id)
        except Exception:
            # Worker not running in dev/test — non-fatal, same as the
            # direct-call behavior this replaces.
            logger.debug(
                "ClaimsHandler could not dispatch analyze_claim_task for claim %s",
                claim_id,
            )
