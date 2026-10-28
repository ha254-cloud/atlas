from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.dashboard.analytics import AnalyticsRepository
from app.models.appeal import Appeal, AppealStatus
from app.models.claim import Claim
from app.models.denial import Denial
from app.models.payer import Payer
from app.models.recovery_case import RecoveryCase, RecoveryStatus


@dataclass
class ToolResult:
    answer: str
    data: Any
    evidence: list[dict] = field(default_factory=list)
    navigation_path: str | None = None


class CopilotToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[[Session, int, dict], ToolResult]] = {}

    def register(self, name: str, tool: Callable[[Session, int, dict], ToolResult]) -> None:
        self._tools[name] = tool

    def execute(self, name: str, db: Session, organization_id: int, arguments: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unsupported Copilot tool: {name}")
        return tool(db, organization_id, arguments)


def _money(value: Decimal | float | int) -> str:
    return f"KSh {float(value):,.0f}"


def search_claims(db: Session, organization_id: int, arguments: dict) -> ToolResult:
    query = (
        db.query(Claim)
        .options(joinedload(Claim.payer))
        .filter(Claim.organization_id == organization_id)
    )
    if arguments.get("status"):
        status = str(arguments["status"]).lower()
        if status == "unpaid":
            query = query.filter(Claim.paid_amount < Claim.billed_amount)
        else:
            query = query.filter(Claim.status == status)
    if arguments.get("priority"):
        query = query.filter(Claim.priority == arguments["priority"])
    if arguments.get("provider"):
        query = query.filter(Claim.provider.ilike(f"%{arguments['provider']}%"))
    if arguments.get("min_amount") is not None:
        query = query.filter(Claim.billed_amount >= Decimal(str(arguments["min_amount"])))
    total = query.count()
    rows = query.order_by(Claim.billed_amount.desc()).limit(25).all()
    data = [
        {
            "id": row.id,
            "claim_number": row.claim_number,
            "payer": row.payer.name,
            "status": row.status,
            "priority": row.priority.value,
            "billed_amount": float(row.billed_amount),
            "paid_amount": float(row.paid_amount or 0),
            "outstanding_amount": float(row.billed_amount - (row.paid_amount or Decimal("0"))),
            "provider": row.provider,
        }
        for row in rows
    ]
    total_outstanding = sum(item["outstanding_amount"] for item in data)
    qualifiers = []
    if arguments.get("status"):
        qualifiers.append(str(arguments["status"]))
    if arguments.get("provider"):
        qualifiers.append(f"provider text matching “{arguments['provider']}”")
    if arguments.get("min_amount") is not None:
        qualifiers.append(f"billed amount at least {_money(arguments['min_amount'])}")
    scope = ", ".join(qualifiers) or "the current filters"
    answer = (
        f"I found {total} claims matching {scope}. The first {len(data)} represent "
        f"{_money(total_outstanding)} in outstanding balances."
    )
    return ToolResult(
        answer=answer,
        data={"total": total, "claims": data},
        evidence=[
            {
                "label": item["claim_number"],
                "path": f"/claims/{item['id']}",
                "value": item["outstanding_amount"],
            }
            for item in data[:5]
        ],
        navigation_path="/claims",
    )


def top_recovery_opportunities(db: Session, organization_id: int, arguments: dict) -> ToolResult:
    limit = min(max(int(arguments.get("limit", 20)), 1), 25)
    rows = (
        db.query(RecoveryCase, Claim, Payer)
        .join(Claim, RecoveryCase.claim_id == Claim.id)
        .join(Payer, Claim.payer_id == Payer.id)
        .filter(
            RecoveryCase.organization_id == organization_id,
            RecoveryCase.status.in_(
                [RecoveryStatus.OPEN, RecoveryStatus.IN_PROGRESS, RecoveryStatus.APPEALED]
            ),
        )
        .order_by(RecoveryCase.recovery_score.desc(), RecoveryCase.estimated_value.desc())
        .limit(limit)
        .all()
    )
    items = [
        {
            "claim_id": claim.id,
            "claim_number": claim.claim_number,
            "payer": payer.name,
            "priority": claim.priority.value,
            "recovery_score": float(case.recovery_score),
            "estimated_recovery": float(case.estimated_value),
            "service_date": claim.service_date.isoformat(),
        }
        for case, claim, payer in rows
    ]
    potential = sum(item["estimated_recovery"] for item in items)
    top_payer = items[0]["payer"] if items else None
    answer = (
        f"The top {len(items)} recovery opportunities represent {_money(potential)} in estimated recovery. "
        + (
            f"The highest-ranked claim is with {top_payer}."
            if top_payer
            else "There are no open recovery opportunities."
        )
    )
    return ToolResult(
        answer=answer,
        data={"count": len(items), "potential_recovery": potential, "claims": items},
        evidence=[
            {
                "label": item["claim_number"],
                "path": f"/claims/{item['claim_id']}",
                "value": item["estimated_recovery"],
            }
            for item in items[:5]
        ],
        navigation_path="/recovery",
    )


def pending_appeals(db: Session, organization_id: int, arguments: dict) -> ToolResult:
    statuses = [AppealStatus.REVIEW, AppealStatus.APPROVED, AppealStatus.SUBMITTED]
    rows = (
        db.query(Appeal)
        .filter(
            Appeal.organization_id == organization_id,
            Appeal.status.in_(statuses),
        )
        .order_by(Appeal.updated_at.desc())
        .limit(25)
        .all()
    )
    counts = {status.value: sum(1 for row in rows if row.status == status) for status in statuses}
    answer = (
        f"There are {len(rows)} active appeals in this view: {counts['review']} awaiting review, "
        f"{counts['approved']} approved for submission, and {counts['submitted']} submitted."
    )
    return ToolResult(
        answer=answer,
        data={
            "count": len(rows),
            "status_counts": counts,
            "appeals": [
                {
                    "id": row.id,
                    "claim_id": row.claim_id,
                    "status": row.status.value,
                    "title": row.title,
                }
                for row in rows
            ],
        },
        evidence=[
            {
                "label": f"Appeal {row.id}",
                "path": f"/claims/{row.claim_id}",
                "value": row.status.value,
            }
            for row in rows[:5]
        ],
        navigation_path="/appeals",
    )


def payer_performance(db: Session, organization_id: int, arguments: dict) -> ToolResult:
    rows = AnalyticsRepository(db, organization_id).payer_performance()
    ranked = sorted(rows, key=lambda row: row.get("recovery_rate_pct", 0), reverse=True)
    leader = ranked[0] if ranked else None
    answer = (
        f"{leader['payer']} has the highest measured appeal success rate at "
        f"{leader.get('recovery_rate_pct', 0):.1f}%."
        if leader
        else "There are not enough payer appeal outcomes to calculate a leader yet."
    )
    return ToolResult(
        answer=answer,
        data=ranked,
        evidence=[
            {"label": row["payer"], "path": "/analytics", "value": row.get("recovery_rate_pct", 0)}
            for row in ranked[:5]
        ],
        navigation_path="/analytics",
    )


def revenue_forecast(db: Session, organization_id: int, arguments: dict) -> ToolResult:
    months = min(max(int(arguments.get("months", 3)), 1), 12)
    rows = AnalyticsRepository(db, organization_id).revenue_forecast(months=months)
    total = sum(float(row.get("expected_recovery", 0)) for row in rows)
    return ToolResult(
        answer=f"Atlas forecasts {_money(total)} in recoveries across the next {months} months based on open cases and current recovery assumptions.",
        data=rows,
        evidence=[
            {
                "label": row.get("month", "Forecast period"),
                "path": "/analytics",
                "value": row.get("expected_recovery", 0),
            }
            for row in rows
        ],
        navigation_path="/analytics",
    )


def denial_trends(db: Session, organization_id: int, arguments: dict) -> ToolResult:
    now = datetime.utcnow()
    current_start = now - timedelta(days=30)
    prior_start = now - timedelta(days=60)
    provider = arguments.get("provider")

    def counts(start: datetime, end: datetime):
        query = (
            db.query(Denial.denial_type, Payer.name, func.count(Denial.id))
            .join(Claim, Denial.claim_id == Claim.id)
            .join(Payer, Claim.payer_id == Payer.id)
            .filter(
                Denial.organization_id == organization_id,
                Denial.created_at >= start,
                Denial.created_at < end,
            )
        )
        if provider:
            query = query.filter(Claim.provider.ilike(f"%{provider}%"))
        return query.group_by(Denial.denial_type, Payer.name).all()

    current = counts(current_start, now)
    prior = counts(prior_start, current_start)
    current_total = sum(row[2] for row in current)
    prior_total = sum(row[2] for row in prior)
    change = (
        ((current_total - prior_total) / prior_total * 100)
        if prior_total
        else (100.0 if current_total else 0.0)
    )
    denial_types: dict[str, int] = {}
    payers: dict[str, int] = {}
    for denial_type, payer, count in current:
        key = denial_type.value
        denial_types[key] = denial_types.get(key, 0) + count
        payers[payer] = payers.get(payer, 0) + count
    top_type = max(denial_types, key=denial_types.get) if denial_types else None
    top_payer = max(payers, key=payers.get) if payers else None
    scope = f"claims whose provider text matches “{provider}”" if provider else "all claims"
    answer = (
        f"For {scope}, Atlas recorded {current_total} denials in the last 30 days versus {prior_total} in the prior 30 days "
        f"({change:+.1f}%)."
    )
    if top_type:
        answer += f" The leading category is {top_type.replace('_', ' ')}"
        if top_payer:
            answer += f", and {top_payer} accounts for the most denials"
        answer += "."
    return ToolResult(
        answer=answer,
        data={
            "current_count": current_total,
            "prior_count": prior_total,
            "change_pct": round(change, 1),
            "by_type": denial_types,
            "by_payer": payers,
            "provider_filter": provider,
        },
        evidence=[{"label": "Denial analytics", "path": "/analytics", "value": current_total}],
        navigation_path="/analytics",
    )


registry = CopilotToolRegistry()
registry.register("search_claims", search_claims)
registry.register("top_recovery_opportunities", top_recovery_opportunities)
registry.register("pending_appeals", pending_appeals)
registry.register("payer_performance", payer_performance)
registry.register("revenue_forecast", revenue_forecast)
registry.register("denial_trends", denial_trends)
