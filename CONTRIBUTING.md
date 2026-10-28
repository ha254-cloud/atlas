# Contributing to Atlas

Atlas changes must be reviewable as healthcare and financial system changes, not only as code changes.

## Before Coding

1. Read `BUILD_STATUS.md` and continue its active batch and acceptance slice.
2. Read `ROADMAP.md`, `DATABASE_SCHEMA.md`, and `API_SPEC.md` for the frozen sequence,
   physical schema, and HTTP surface.
3. Search the current code, routes, workers, pages, and tests for the requested behavior.
4. Identify the canonical owner in `docs/module-registry.md` and extend it.
5. Record which existing surfaces were checked and whether the change needs a new table.
6. Define acceptance criteria, tenant boundary, permissions, audit events, failure behavior, and observability.
7. Create an ADR for a new first-class module or durable architecture, security, data, integration, or intentional-debt decision.
8. Confirm whether the change alters a public API, event, schema, configuration, or deployment contract.

Do not create a parallel module because a specification uses different names. New
transports feed canonical services; new pages use canonical APIs; workers invoke
domain services. The repository-root `app/` tree is not a production source root.

## Development

Keep routers thin, repositories tenant-scoped, and business rules in services. Use connector interfaces for vendors and `AIGateway` for AI providers. AI-generated appeals always require explicit human review, and approval never submits automatically.

Add a migration for schema changes. Never edit an applied migration. Preserve existing data and document rollback behavior.
Update `DATABASE_SCHEMA.md` with every table change and `API_SPEC.md` with every route
change. `tests/test_architecture_contracts.py` must remain green.

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
- Owning module and engine, with the checked registry entry
- Existing implementation surfaces examined and why a new table/module was or was not required
- Security, tenant, audit, and PHI/PII impact
- API/event/schema/configuration changes
- Deployment and rollback steps
- Tests and commands run
- Monitoring and alert changes
- Documentation updated
- Residual risk and follow-up owner

Use `docs/definition-of-done.md` as the review checklist. Update `docs/release-plan.md` only when executable evidence changes readiness.
Update `BUILD_STATUS.md` with the completed acceptance slice and next action; do not
mark a module Complete based only on file presence or partial tests.

## Review Standard

Reviewers block changes that duplicate a registered capability, weaken tenant isolation,
bypass RBAC, introduce unaudited material mutations, call vendor/AI SDKs from domain
code, embed policy in literals, lack rollback, or couple approval to automatic appeal
submission.
