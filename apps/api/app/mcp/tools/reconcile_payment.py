from sqlalchemy.orm import Session

from app.claims.repository import ClaimRepository
from app.mcp.schemas.responses import MCPResponse
from app.mcp.tools import BaseTool


class ReconcilePaymentTool(BaseTool):
    """
    Apply a payment to a claim and update its paid_amount.
    Delegates to ClaimService — no business logic here.
    """

    name = "reconcile_payment"

    async def execute(
        self,
        db: Session,
        organization_id: int,
        claim_id: int,
        payment_amount: float,
        payment_reference: str | None = None,
        **_,
    ) -> MCPResponse:
        repo = ClaimRepository(db, organization_id)
        claim = repo.get(claim_id)

        if claim is None:
            return self._err(f"Claim {claim_id} not found")

        previous_paid = float(claim.paid_amount or 0)
        new_paid = previous_paid + payment_amount

        repo.update(claim_id, paid_amount=new_paid)

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(claim)

        return self._ok(
            {
                "claim_id": claim_id,
                "payment_reference": payment_reference,
                "payment_applied": payment_amount,
                "previous_paid": previous_paid,
                "total_paid": float(claim.paid_amount),
                "billed_amount": float(claim.billed_amount),
                "balance": float(claim.billed_amount) - float(claim.paid_amount),
            }
        )
