"""
AI call cost/usage tracking.

Kept deliberately decoupled from the caller's own DB session/transaction —
logging an AI call is a cross-cutting observability concern, not part of
the claim/appeal/document write it happened to originate from, and must
never fail (or slow down) the actual feature if logging has a problem.

Attribution (organization_id/claim_id) is threaded through via a
contextvar rather than new required parameters on every AI call signature
— this keeps `AIProvider.generate()`/`AIGateway.generate()` callable
exactly as before for every existing caller (including test doubles that
only implement `generate(prompt, system=None)`), while still letting the
few call sites that know the organization/claim wrap themselves with
`ai_call_context(...)` to get attributed cost logs.
"""

import contextvars
import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func

from app.ai.exceptions import AIProviderError
from app.core.config import settings

logger = logging.getLogger(__name__)

_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "ai_call_context", default=None
)


@contextmanager
def ai_call_context(*, organization_id: int, claim_id: int | None = None):
    """Wrap a block of code that makes one or more AI Gateway calls so any
    resulting AICallLog rows are attributed to this organization/claim."""
    token = _context.set({"organization_id": organization_id, "claim_id": claim_id})
    try:
        yield
    finally:
        _context.reset(token)


def current_context() -> dict:
    return _context.get() or {}


# Rough, approximate USD-per-1K-token rates — NOT pulled from a live
# pricing API. Update this table when provider pricing changes; treat
# `AICallLog.cost_usd` as directionally useful for spotting usage trends
# and expensive tasks, not as an exact invoice figure.
_PRICING_PER_1K_TOKENS: dict[str, dict[str, Decimal]] = {
    "gpt-4.1": {"input": Decimal("0.002"), "output": Decimal("0.008")},
    "gpt-4.1-mini": {"input": Decimal("0.0004"), "output": Decimal("0.0016")},
}
_DEFAULT_RATES = {"input": Decimal("0.002"), "output": Decimal("0.008")}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    rates = _PRICING_PER_1K_TOKENS.get(model, _DEFAULT_RATES)
    cost = (Decimal(input_tokens) / Decimal(1000)) * rates["input"] + (
        Decimal(output_tokens) / Decimal(1000)
    ) * rates["output"]
    return cost.quantize(Decimal("0.000001"))


def enforce_monthly_budget(*, task: str, provider: str) -> None:
    budget = settings.AI_MONTHLY_BUDGET_USD
    if budget <= 0:
        return

    from app.db.database import SessionLocal
    from app.models.ai_call_log import AICallLog

    month_start = datetime.now(UTC).replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    db = SessionLocal()
    try:
        spent = (
            db.query(func.coalesce(func.sum(AICallLog.cost_usd), 0))
            .filter(AICallLog.created_at >= month_start)
            .scalar()
        )
    except Exception as exc:
        logger.exception("Failed to verify the monthly AI budget")
        raise AIProviderError(
            "AI is temporarily unavailable because its spending limit could not be verified",
            task=task,
            provider=provider,
        ) from exc
    finally:
        db.close()

    spent_usd = Decimal(str(spent or 0))
    if spent_usd >= budget:
        raise AIProviderError(
            f"AI monthly budget of ${budget:.2f} has been reached",
            task=task,
            provider=provider,
        )


def log_ai_call(
    *,
    task: str,
    provider: str,
    model: str,
    duration_ms: int,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    prompt_version: str | None = None,
    cache_hit: bool = False,
) -> None:
    """Persist tenant-attributed AI usage without affecting the AI result."""
    ctx = current_context()
    organization_id = ctx.get("organization_id")
    if organization_id is None:
        logger.error(
            "AI usage was not persisted because organization context is missing",
            extra={"ai_task": task, "ai_provider": provider, "ai_model": model},
        )
        return

    cost_usd = None
    if input_tokens is not None and output_tokens is not None:
        cost_usd = estimate_cost_usd(model, input_tokens, output_tokens)

    try:
        from app.db.database import SessionLocal
        from app.models.ai_call_log import AICallLog

        db = SessionLocal()
        try:
            db.add(
                AICallLog(
                    organization_id=organization_id,
                    claim_id=ctx.get("claim_id"),
                    task=task,
                    provider=provider,
                    model=model,
                    prompt_version=prompt_version,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                    duration_ms=duration_ms,
                    cache_hit=cache_hit,
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("Failed to persist AI call log (non-fatal)")
