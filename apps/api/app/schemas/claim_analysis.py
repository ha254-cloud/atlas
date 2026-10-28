from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClaimAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_score: int = Field(ge=0, le=100)
    recovery_probability: float = Field(ge=0.0, le=1.0)
    priority: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    required_documents: list[str]
