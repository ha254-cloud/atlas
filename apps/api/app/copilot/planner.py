import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    tool_name: str | None = None
    arguments: dict | None = None
    action: str | None = None


def _amount(text: str) -> float | None:
    match = re.search(r"(?:(?:ksh|kes|\$)\s*)?([\d,]+(?:\.\d+)?)\s*([km])?", text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return value


def plan_message(message: str, context: dict | None = None) -> Plan:
    text = " ".join(message.strip().split())
    lowered = text.lower()
    context = context or {}

    assignment = re.search(r"assign all (.+?) claims to ([\w .'-]+)$", text, re.IGNORECASE)
    if assignment:
        return Plan(
            action="assign_claims",
            arguments={
                "provider": assignment.group(1).strip(),
                "assignee": assignment.group(2).strip(),
            },
        )

    if lowered.startswith("only those") and context.get("tool_name") == "search_claims":
        arguments = dict(context.get("arguments") or {})
        amount = _amount(lowered)
        if amount is not None:
            arguments["min_amount"] = amount
        return Plan(tool_name="search_claims", arguments=arguments)

    if any(
        phrase in lowered
        for phrase in [
            "prioritize today",
            "top recovery opportunities",
            "should my team prioritize",
        ]
    ):
        amount = _amount(lowered)
        return Plan(
            tool_name="top_recovery_opportunities",
            arguments={"limit": int(amount) if amount and amount <= 25 else 20},
        )
    if "pending appeals" in lowered or "appeals pending" in lowered:
        return Plan(tool_name="pending_appeals", arguments={})
    if (
        "highest recovery rate" in lowered
        or "best payer" in lowered
        or "highest denial payers" in lowered
    ):
        return Plan(tool_name="payer_performance", arguments={})
    if "forecast" in lowered or "likely to recover" in lowered:
        months = 3 if "quarter" in lowered else 6 if "six month" in lowered else 3
        return Plan(tool_name="revenue_forecast", arguments={"months": months})
    trend = re.search(r"why (?:are|did) (.+?) denials? (?:increasing|increase)", lowered)
    if trend:
        return Plan(tool_name="denial_trends", arguments={"provider": trend.group(1).strip()})
    if "denial" in lowered and any(word in lowered for word in ["increase", "trend", "why"]):
        return Plan(tool_name="denial_trends", arguments={})
    if "claim" in lowered or "unpaid" in lowered:
        arguments: dict = {}
        if "unpaid" in lowered:
            arguments["status"] = "unpaid"
        if "high-priority" in lowered or "high priority" in lowered:
            arguments["priority"] = "high"
        amount = _amount(lowered)
        if amount is not None:
            arguments["min_amount"] = amount
        return Plan(tool_name="search_claims", arguments=arguments)
    return Plan()
