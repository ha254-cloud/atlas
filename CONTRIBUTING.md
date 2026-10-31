# Contributing to Atlas

Atlas changes must be reviewable as healthcare and financial system changes, not only as code changes.

## Before Coding

1. Identify the owning module and engine in `docs/engineering-principles.md`.
2. Define acceptance criteria, tenant boundary, permissions, audit events, failure behavior, and observability.
3. Create an ADR for durable architecture, security, data, integration, or intentional-debt decisions.
4. Confirm whether the change alters a public API, event, schema, configuration, or deployment contract.

## Development

Keep routers thin, repositories tenant-scoped, and business rules in services. Use connector interfaces for vendors and `AIGateway` for AI providers. AI-generated appeals always require explicit human review, and approval never submits automatically.

Add a migration for schema changes. Never edit an applied migration. Preserve existing data and document rollback behavior.

## Verification

Run the narrowest relevant tests while developing, then the repository gates before review:

```bash
make quality
```

For a targeted backend iteration:

```bash
make lint-api
make test-api
make migration-heads
```

For web changes:

```bash
make check-web
```

## Pull Request Evidence

The pull request must state:

- User and business outcome
- Owning module and engine
- Security, tenant, audit, and PHI/PII impact
- API/event/schema/configuration changes
- Deployment and rollback steps
- Tests and commands run
- Monitoring and alert changes
- Documentation updated
- Residual risk and follow-up owner

Use `docs/definition-of-done.md` as the review checklist. Update `docs/release-plan.md` only when executable evidence changes readiness.

## Review Standard

Reviewers block changes that weaken tenant isolation, bypass RBAC, introduce unaudited material mutations, call vendor/AI SDKs from domain code, embed policy in literals, lack rollback, or couple approval to automatic appeal submission.
