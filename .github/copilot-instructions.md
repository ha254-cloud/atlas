# Atlas Repository Instructions

Atlas is a healthcare revenue recovery platform intended for long-term operation in regulated environments. Treat every change as potentially reviewable by hospitals, insurers, regulators, auditors, and future maintainers.

## Required Engineering Standard

- Do not declare a feature complete without models, schemas, repository, service, API or event entrypoint, tests, documentation, deployment impact, security review, audit behavior, and observability.
- Keep domain behavior inside its owning module. HTTP routers validate and translate; repositories query; services enforce business rules.
- Prefer events between modules. Direct synchronous calls are acceptable only when the caller requires an immediate result or a shared transaction. Document the reason when introducing a new cross-domain call.
- Preserve explicit human approval for AI-generated appeals. Never add automatic submission from appeal generation or approval.
- Scope every tenant-owned query by `organization_id` derived from authenticated context, never client input.
- Require authentication and the narrowest RBAC permission on every non-public API.
- Record material mutations with actor, timestamp, before, after, reason, organization, and correlation ID when the infrastructure supports it. Never mutate versioned records in place.
- Route AI calls through `AIGateway`; never call a provider SDK from domain code. Prompts and model selections must be versioned and configurable.
- Implement integrations through registered connector interfaces. Domain services must not import vendor clients directly.
- Put payer rules, fee percentages, provider/model names, polling intervals, and timeouts in typed configuration or tenant settings. Do not add unexplained literals.
- Add migrations for schema changes and verify Alembic has exactly one head.
- Maintain backward compatibility deliberately. If a public API or persisted contract changes, document migration and rollback behavior.

## Completion Gate

Before closing implementation work:

1. Run focused tests for the changed behavior.
2. Run adjacent regression tests based on blast radius.
3. Run Ruff for Python changes and TypeScript type-check plus production build for web changes.
4. Check editor diagnostics.
5. Update relevant documentation and `docs/release-plan.md` when readiness changes.
6. Report commands run, migration state, residual risks, and anything not validated.

Use `docs/engineering-principles.md`, `docs/definition-of-done.md`, and `docs/release-plan.md` as the governing sources of truth.
