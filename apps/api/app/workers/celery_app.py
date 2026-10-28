from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

celery = Celery(
    "atlas",
    broker="redis://redis:6379/0",
    # No result backend: nothing in the codebase ever calls .get()/checks
    # AsyncResult state — every call site is a fire-and-forget .delay().
    # Configuring a backend anyway (as before) makes apply_async() touch
    # Redis a second time to register initial task state, and that backend
    # client retries connection errors ~20x with a 1s interval by default
    # (celery.backends.redis's retry policy) — none of the broker fail-fast
    # settings below apply to it, so it alone added ~8-20s to every event
    # publish once Sprint 8 wired handlers into every test importing
    # app.main. Since nothing reads results, just don't configure one.
    backend=None,
    # Without this, the worker process never imports app.workers.tasks, so
    # none of the @celery.task-decorated functions get registered — tasks
    # dispatched via .delay() would sit in the queue forever as "unregistered".
    include=[
        "app.workers.tasks",
        "app.tasks.ai_analysis",
        "app.tasks.generate_appeal",
    ],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_ignore_result=True,
    # Fail fast instead of retrying forever when the broker is unreachable
    # (e.g. in a test/CI container run without the Redis service attached).
    # Sprint 8's event handlers dispatch Celery tasks reactively from
    # in-process event publishing (ClaimsHandler, WebhookHandler, etc.) and
    # always wrap `.delay()` in try/except — but that only helps if the
    # failure actually raises quickly rather than hanging on connection
    # retries, so `.delay()` must never block indefinitely.
    broker_connection_retry_on_startup=False,
    broker_connection_timeout=2,
    broker_connection_max_retries=1,
    beat_schedule={
        "payer-submission-status-poll": {
            "task": "tasks.check_pending_payer_submissions",
            "schedule": timedelta(minutes=5),
        },
        "payer-follow-up-sweep": {
            "task": "tasks.check_payer_follow_ups",
            "schedule": timedelta(hours=1),
        },
        "monthly-recovery-invoices": {
            "task": "tasks.generate_monthly_recovery_invoices",
            "schedule": crontab(day_of_month=1, hour=8, minute=0),
        },
        "sftp-claim-import": {
            "task": "tasks.schedule_sftp_syncs",
            "schedule": timedelta(hours=4),
        },
        "pending-workflow-events": {
            "task": "tasks.requeue_pending_workflow_events",
            "schedule": timedelta(minutes=1),
        },
        "task-intelligence-sla-sweep": {
            "task": "tasks.check_task_slas",
            "schedule": timedelta(hours=1),
        },
        "recovery-lifecycle-reconciliation": {
            "task": "tasks.reconcile_recovery_lifecycles",
            "schedule": timedelta(hours=1),
        },
    },
)
