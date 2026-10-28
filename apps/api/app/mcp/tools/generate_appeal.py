from sqlalchemy.orm import Session

from app.ai.appeal_generator import AppealGenerator
from app.claims.repository import ClaimRepository
from app.mcp.schemas.responses import MCPResponse
from app.mcp.tools import BaseTool


class GenerateAppealTool(BaseTool):
    """
    Generate an appeal letter for a denied claim.
    Delegates to AppealGenerator — no business logic here.
    """

    name = "generate_appeal"

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

        appeal_text = await AppealGenerator().generate_appeal(claim)
        return self._ok({"claim_id": claim_id, "appeal": appeal_text})
