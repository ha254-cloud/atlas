"""
Registers every built-in event handler onto the process-wide EventBus.

Call `register_all()` once at process startup. It's idempotent (safe to
call more than once — e.g. once from app.main for the API process and once
from app.workers.celery_app for the worker process) since events can be
published from either process and each needs its own handlers registered.
"""

from app.events.bus import ALL_EVENTS, event_bus
from app.events.event_types import EventType
from app.events.handlers.analytics import AnalyticsHandler
from app.events.handlers.appeals import AppealGeneratedHandler
from app.events.handlers.claims import ClaimsHandler
from app.events.handlers.dashboard import DashboardHandler
from app.events.handlers.decisions import DecisionHandler
from app.events.handlers.notifications import NotificationHandler
from app.events.handlers.webhooks import WebhookHandler
from app.events.handlers.workflows import WorkflowTriggerHandler
from app.tasks.handlers import EVENT_TASKS, TaskEventHandler
from app.workflows.events import SUPPORTED_WORKFLOW_TRIGGERS

_registered = False


def register_all() -> None:
    global _registered
    if _registered:
        return

    # Dashboard + webhooks react to every event.
    event_bus.subscribe(ALL_EVENTS, DashboardHandler())
    event_bus.subscribe(ALL_EVENTS, WebhookHandler())

    # Everyone else reacts to specific events.
    event_bus.subscribe(EventType.CLAIM_IMPORTED, ClaimsHandler())
    event_bus.subscribe(EventType.CLAIM_ANALYZED, DecisionHandler())
    event_bus.subscribe(EventType.CLAIM_ANALYZED, NotificationHandler())
    event_bus.subscribe(EventType.APPEAL_GENERATED, AppealGeneratedHandler())
    event_bus.subscribe(EventType.APPEAL_GENERATED, NotificationHandler())
    event_bus.subscribe(EventType.APPEAL_APPROVED, NotificationHandler())
    event_bus.subscribe(EventType.PAYMENT_RECEIVED, AnalyticsHandler())
    workflow_handler = WorkflowTriggerHandler()
    for trigger in SUPPORTED_WORKFLOW_TRIGGERS:
        event_bus.subscribe(trigger, workflow_handler)
    task_handler = TaskEventHandler()
    for trigger in EVENT_TASKS:
        event_bus.subscribe(trigger, task_handler)

    _registered = True
