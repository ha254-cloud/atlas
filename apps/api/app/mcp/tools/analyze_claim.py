from sqlalchemy.orm import Session

from app.ai.claim_analyzer import ClaimAnalyzer
from app.claims.repository import ClaimRepository
from app.mcp.schemas.responses import MCPResponse
from app.mcp.tools import BaseTool


class AnalyzeClaimTool(BaseTool):
    """
    Run AI analysis on a claim scoped to the caller's organization.
    Delegates entirely to ClaimAnalyzer — no business logic here.
    """

    name = "analyze_claim"

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

        result = await ClaimAnalyzer().analyze(claim)
        return self._ok({"claim_id": claim_id, "analysis": result})
