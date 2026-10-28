from typing import Any

from pydantic import BaseModel


class MCPToolRequest(BaseModel):
    """Envelope sent by any MCP client to invoke a tool."""

    params: dict[str, Any] = {}


class AnalyzeClaimRequest(BaseModel):
    claim_id: int


class EstimateRecoveryRequest(BaseModel):
    claim_id: int
    denial_probability: float = 0.5
    claim_age_days: int = 0


class GenerateAppealRequest(BaseModel):
    claim_id: int


class ClassifyDenialRequest(BaseModel):
    claim_id: int


class CheckStatusRequest(BaseModel):
    claim_id: int


class SyncClaimsRequest(BaseModel):
    connector: str  # "epic" | "athena" | "eclinicalworks"
    since_days: int = 30


class ReconcilePaymentRequest(BaseModel):
    claim_id: int
    payment_amount: float
    payment_reference: str | None = None
