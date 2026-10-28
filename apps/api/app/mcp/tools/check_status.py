from sqlalchemy.orm import Session

from app.claims.repository import ClaimRepository
from app.mcp.schemas.responses import MCPResponse
from app.mcp.tools import BaseTool


class CheckStatusTool(BaseTool):
    """
    Return the current status, recovery cases, and denials for a claim.
    Read-only — no mutations.
    """

    name = "check_status"

    async def execute(
        self,
        db: Session,
        organization_id: int,
        claim_id: int,
        **_,
    ) -> MCPResponse:
        claim = ClaimRepository(db, organization_id).get(claim_id)
        if claim is None:
            return self._err(f"Claim {claim_id} not found")

        return self._ok(
            {
                "claim_id": claim.id,
                "status": claim.status,
                "billed_amount": str(claim.billed_amount),
                "paid_amount": str(claim.paid_amount),
                "recovery_cases": [
                    {
                        "id": rc.id,
                        "status": rc.status.value,
                        "estimated_value": str(rc.estimated_value),
                    }
                    for rc in getattr(claim, "recovery_cases", [])
                ],
                "denials": [
                    {
                        "id": d.id,
                        "denial_type": d.denial_type.value if d.denial_type else None,
                        "description": d.description,
                    }
                    for d in getattr(claim, "denials", [])
                ],
            }
        )
