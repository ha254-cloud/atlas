from sqlalchemy.orm import Session

from app.ai.denial_classifier import DenialClassifier
from app.claims.repository import ClaimRepository
from app.mcp.schemas.responses import MCPResponse
from app.mcp.tools import BaseTool


class ClassifyDenialTool(BaseTool):
    """
    Classify the denial reason for a claim using AI.
    Delegates to DenialClassifier — no business logic here.
    """

    name = "classify_denial"

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

        classification = await DenialClassifier().classify(claim)
        return self._ok({"claim_id": claim_id, "classification": classification})
