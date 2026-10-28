# Definition of Done

## Feature Gate

A feature is complete only when every applicable item is checked and evidence is linked in the pull request.

### Domain Design

- [ ] Owning module and engine are identified.
- [ ] Every persisted table is classified as global, directly tenant-owned, or parent-scoped.
- [ ] Models, constraints, indexes, and migration are reviewed.
- [ ] Schemas reject unknown or invalid input where appropriate.
- [ ] Repository methods are tenant-scoped.
- [ ] API, task, event, AI, integration, report, cache, storage, and audit tenant context is defined.
- [ ] Service owns business rules and transaction boundaries.
- [ ] API is thin, authenticated, authorized, and documented.
- [ ] Events are versioned, post-commit, idempotent, and documented.
- [ ] Configuration replaces payer, model, fee, timeout, and schedule literals.

### Data and Audit

- [ ] Material records are versioned or immutability is explained.
- [ ] Mutations record actor, before, after, reason, timestamp, and correlation ID.
- [ ] Retention, deletion, and rollback behavior are defined.
- [ ] PHI/PII and financial fields are classified and redacted from logs.

### Verification

- [ ] Unit tests cover rules and calculations.
- [ ] Repository tests cover tenant isolation and constraints.
- [ ] API tests cover authentication, RBAC, same-tenant access, cross-tenant denial, validation, and error mapping.
- [ ] Background-task tests reject missing or mismatched organization ownership.
- [ ] Event tests cover duplicate delivery and failed consumers.
- [ ] Integration tests cover the user-visible workflow.
- [ ] Migration upgrade is tested against PostgreSQL and Alembic has one head.
- [ ] Frontend changes pass type-check, production build, and responsive browser checks.
- [ ] Focused lint and adjacent regression tests pass.

### Operations

- [ ] Structured logs and metrics include correlation and tenant context.
- [ ] Health, timeout, retry, idempotency, and failure behavior are defined.
- [ ] Alerts have thresholds, owners, and runbooks.
- [ ] Deployment and rollback steps are documented.
- [ ] Secrets and required configuration fail closed in production.

### Documentation

- [ ] API/OpenAPI examples are current.
- [ ] Architecture and data-flow docs are updated.
- [ ] Operator runbook and support diagnostics are updated.
- [ ] Release plan readiness and residual risks are updated.
- [ ] An ADR exists for durable or cross-cutting decisions.

## Module Completeness Matrix

Every first-class module maintains this structure where applicable:

```text
module/
  models.py or owned models
  schemas.py
  repository.py
  service.py
  router.py and/or handlers.py
  tests/
  README.md or docs/<module>.md
```

Shared model placement is allowed, but ownership must be documented. Compatibility wrappers may remain during migration, with a removal milestone.

## Release Gate

A release candidate requires:

- All milestone blockers closed or explicitly accepted by named release owner.
- CI green on the release commit.
- Database backup and rollback rehearsal.
- Security and tenant-isolation review.
- End-to-end workflow evidence in a production-like environment.
- Monitoring dashboards and alerts tested.
- Known limitations documented for users and support.

Passing tests alone does not make a release production-ready.
