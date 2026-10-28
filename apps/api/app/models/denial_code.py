from enum import Enum

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base
from app.models.denial import DenialType


class DenialCodeSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DenialCodeRecoverability(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DenialCode(Base, TimestampMixin):
    """
    Atlas' denial knowledge base — standardized payer denial/adjustment
    reason codes (e.g. CARC codes like CO16, CO29, CO50) mapped to a
    category, a plain-English description, and a recommended recovery
    strategy.

    This is reference data shared across every organization (the codes
    themselves are industry-standard, not tenant-specific). The AI
    analysis pipeline looks a claim's denial code up here for grounding
    context instead of relying on the LLM to "remember" what each code
    means — that keeps results consistent and makes the system easy to
    update as payer rules evolve, without ever touching a prompt.
    """

    __tablename__ = "denial_codes"

    id: Mapped[int] = mapped_column(primary_key=True)

    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    category: Mapped[DenialType] = mapped_column(SqlEnum(DenialType), index=True, nullable=False)

    description: Mapped[str] = mapped_column(String(500), nullable=False)

    recovery_strategy: Mapped[str] = mapped_column(String(500), nullable=False)

    # Guidance aimed at the AI analyzer specifically (how to weigh
    # recovery_probability/confidence for this code) — distinct from
    # `recovery_strategy`, which is the human-facing recommended action.
    ai_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Richer operational intelligence, layered on top of the Stage-1 fields
    # above — how bad the denial typically is, how likely it is to be
    # recovered, and what it takes to recover it, so the AI (and the
    # dashboard) can reason with structured data instead of prose alone.
    severity: Mapped[DenialCodeSeverity | None] = mapped_column(
        SqlEnum(DenialCodeSeverity), nullable=True
    )

    recoverability: Mapped[DenialCodeRecoverability | None] = mapped_column(
        SqlEnum(DenialCodeRecoverability), nullable=True
    )

    # Historical/benchmark recovery rate for this code, as a percentage (0-100).
    typical_recovery_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # List[str] of documents typically required to support an appeal/resubmission.
    required_documents: Mapped[list | None] = mapped_column(JSON, nullable=True)

    typical_resolution_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # List[str] of payers this code is commonly seen from.
    common_payers: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # List[str] of citations/authoritative sources for this code's definition.
    references: Mapped[list | None] = mapped_column(JSON, nullable=True)
