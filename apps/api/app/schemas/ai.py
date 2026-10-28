from pydantic import BaseModel


class DenialAnalysis(BaseModel):
    denial_type: str
    confidence: float
    reason: str
    recommended_action: str
