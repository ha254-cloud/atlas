from sqlalchemy.orm import Session

from app.claims.repository import ClaimRepository
from app.mcp.schemas.responses import MCPResponse
from app.mcp.tools import BaseTool
from app.recovery.engine import RecoveryEngine


class EstimateRecoveryTool(BaseTool):
    """
    Estimate the recovery opportunity for a claim.
    Delegates to RecoveryEngine — no business logic here.
    """

    name = "estimate_recovery"

    async def execute(
        self,
        db: Session,
        organization_id: int,
        claim_id: int,
        denial_probability: float = 0.5,
        claim_age_days: int = 0,
        **_,
    ) -> MCPResponse:
        claim = ClaimRepository(db, organization_id).get(claim_id)
        if claim is None:
            return self._err(f"Claim {claim_id} not found")

        opportunity = RecoveryEngine().analyze(claim, denial_probability, claim_age_days)

        if opportunity is None:
            return self._ok(
                {
                    "claim_id": claim_id,
                    "recoverable": False,
                    "reason": "Claim does not meet recovery thresholds",
                }
            )

        return self._ok(
            {
                "claim_id": claim_id,
                "recoverable": True,
                "score": str(opportunity.score),
                "estimated_recovery": str(opportunity.estimated_recovery),
                "balance": str(opportunity.balance),
                "priority": opportunity.priority.value,
                "next_action": opportunity.next_action,
            }
        )
