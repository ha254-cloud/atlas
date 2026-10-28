# Task Intelligence Engine

Atlas Task Intelligence converts claim lifecycle events into prioritized, assigned daily work. It is an operational layer over canonical claims, payers, appeals, payments, and workflows; it does not replace those domain records.

## Lifecycle

```text
Claim analyzed -> task created -> priority scored -> skill/role routed
-> least-loaded eligible user -> work completed -> next task created
```

The event handler creates tasks idempotently for claim analysis, appeal generation and approval, and payment receipt and verification. The database uniqueness boundary is organization, claim, task type, and sequence.

## Priority

Priority is an explainable integer from 0 to 100:

- 60% recovery probability.
- 25% claim value, capped at KES 1,000,000.
- 15% age, capped at 60 days.
- Five-point boost when recovery probability is at least 90%, value is at least KES 500,000, and age is at least 30 days.

For example, a KES 850,000 claim with 96% recovery probability and 67 days outstanding scores 99.

## Assignment

Assignment first determines the required role from task department. Appeals route to appeals specialists, finance tasks to billers, claim work to revenue analysts, and claims at or above the configured high-value threshold route to managers. Payer skills can narrow the candidate set through tenant-owned user skill profiles. Atlas then assigns the least-loaded eligible active user, with user ID as a deterministic tie-breaker.

When no eligible user exists, the task remains `NEW` and visible to managers for assignment. Atlas never assigns a task across organizations.

## SLA And Escalation

Typed organization settings control the default SLA, payer-specific SLA days, payer skill mapping, high-value threshold, and escalation thresholds. Defaults include SHA 35 days, Jubilee 21 days, and Britam 18 days; hospitals must review these against actual contracts and operating procedures.

Celery Beat runs `tasks.check_task_slas` hourly across organizations. Breached tasks become `OVERDUE`; escalation levels notify managers first and owners at later configured thresholds. A database uniqueness constraint prevents duplicate delivery for the same task, recipient, notification type, and level. Managers can also trigger a tenant-scoped sweep through the API.

## API

All routes derive `organization_id` from the authenticated user:

- `GET /api/v1/tasks/queue` supports status, payer, and date-window filters.
- `POST /api/v1/tasks/{id}/transition` enforces legal task transitions and assignee access.
- `POST /api/v1/tasks/{id}/assign` is manager-only.
- `GET /api/v1/tasks/manager` returns open, completed-today, overdue, and completion-time metrics.
- `GET /api/v1/tasks/performance` includes task count, average time, average priority, and claim value context.
- `GET /api/v1/tasks/notifications` returns durable per-user reminders.
- `GET /api/v1/tasks/claims/{claim_id}/timeline` returns immutable before/after task activity.
- `PUT /api/v1/tasks/users/{user_id}/skills` manages skills used for routing.

The web portal exposes these workflows at `/tasks` as `Today's Work`.

## Audit And Observability

Every task creation, assignment, transition, completion, and escalation appends a `task_activities` record containing organization, claim, actor when known, timestamp, before and after state, reason, and correlation ID. Records are append-only. Task lifecycle events are also published through the Atlas event bus for dashboards, webhooks, logs, and tracing.

Performance metrics are operational signals, not employee rankings. Managers must interpret counts alongside priority, claim value, and task complexity.

## Security Review

- Tasks, activities, skills, and notifications are directly tenant-owned with non-null organization foreign keys.
- Repositories scope reads and writes by authenticated organization.
- Assignees must be active users in the same organization.
- Staff can transition only their assigned tasks; owner, admin, and manager roles can manage the organization queue.
- Cross-tenant task access and queue leakage are covered by focused tests.
- No AI provider or payer connector is called by this module.

## Deployment And Rollback

Migration `e9a4c7b2d6f1` creates tasks, task activities, user task skills, and durable task notifications. Deploy API, worker, and Beat from the same build after applying the migration. Downgrade drops Sprint 18 task data and must only be used with an approved data-retention/export decision.

Branch routing is intentionally unavailable. Atlas does not yet have a governed tenant-owned branch model, so persisting an unverifiable `branch_id` would weaken the ownership contract. Branch filters and routing remain blocked on the branch/membership schema in the release plan.