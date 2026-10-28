from datetime import datetime, timedelta

from app.organizations.schemas import TaskIntelligenceSettings


def due_date_for(
    *, payer_code: str | None, payer_name: str, settings: TaskIntelligenceSettings, now: datetime
) -> datetime:
    identifiers = [value.upper() for value in (payer_code, payer_name) if value]
    days = next(
        (settings.payer_sla_days[key] for key in identifiers if key in settings.payer_sla_days),
        settings.default_sla_days,
    )
    return now + timedelta(days=days)


def escalation_level(
    *, due_date: datetime, current_level: int, thresholds: list[int], now: datetime
) -> int:
    if now <= due_date:
        return current_level
    overdue_days = (now - due_date).days
    eligible = sum(overdue_days >= threshold for threshold in thresholds)
    return max(current_level, eligible)
