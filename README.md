# Atlas

Atlas is a Kenya-first, multi-tenant AI Revenue Recovery Platform that turns
denied and underpaid claims into auditable recovery workflows. It complements
rather than replaces hospital information and claims-management systems. One shared Atlas
environment supports independent healthcare organizations with isolated data,
users, configuration, integrations, workflows, analytics, and billing.

> AI-generated appeals are never submitted automatically. Generation, approval, and submission are separate actions with separate permissions and audit records.

## System Shape

Atlas is organized around four engines:

| Engine | Responsibility |
|---|---|
| Intelligence | Claim analysis, denial classification, recovery scoring, appeal generation, and Copilot tools |
| Workflow | Recovery cases, queues, state transitions, approvals, scheduling, and notifications |
| Integration | HIS CSV/SFTP ingestion, payer registry, connector routing, submission, status, and payment reports |
| Revenue | Payment attribution, verified recoveries, fee calculation, invoices, and financial reporting |

Shared platform capabilities provide identity, organization tenancy, RBAC, audit logs, events, documents, configuration, and observability.

Every feature must be organization-aware. A new organization must be onboardable
through configuration and registered integrations without a customer-specific
code change. Recovery accounting and Atlas customer subscription billing are
separate financial domains.

The implemented workflow is:

```text
claim import -> analysis -> appeal generation -> human approval
-> explicit submission -> status tracking -> payment attribution
-> recovery verification -> monthly invoice
```

## Repository

```text
apps/api/       FastAPI application, Celery workers, SQLAlchemy, Alembic
apps/web/       Next.js operations dashboard
packages/       Shared SDK, connector, MCP, and type packages
infrastructure/ Deployment and operational scripts
docs/           Architecture, security, operations, and release governance
```

The root-level `app/` tree contains earlier/shared implementation surfaces. Runtime API changes should follow ownership and entrypoints under `apps/api/app/`; do not duplicate a domain without an explicit migration plan.

## Local Development

Prerequisites: Docker Desktop, Python 3.11, Node.js 20, and GNU Make (or run the equivalent commands from the Makefile).

```bash
make up
make migrate
```

- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Web: `http://localhost:3000`

Copy environment templates where provided and use development-only secrets. Production configuration must use managed secrets and fail closed when required values are absent.

## Quality Gates

```bash
make quality          # API lint/tests, one migration head, web type/lint/build
make lint-api         # Ruff check and format check
make test-api         # Backend test suite
make migration-heads # Assert exactly one Alembic head
make check-web        # Type-check, lint, and production build
```

Focused tests should run before the full gate. CI runs the same classes of checks against PostgreSQL and Redis.

## Engineering Governance

- [Engineering principles](docs/engineering-principles.md)
- [Definition of Done](docs/definition-of-done.md)
- [Release plan](docs/release-plan.md)
- [Contributing](CONTRIBUTING.md)
- [Architecture](docs/architecture.md)
- [Tenant architecture](docs/tenant-architecture.md)
- [Security](docs/security.md)
- [Deployment](docs/deployment.md)
- [API guide](docs/api.md)
- [Database](docs/database.md)
- [Integrations](docs/integrations.md)

OpenAPI and Alembic migrations are the executable sources of truth for runtime API and database contracts. Narrative documentation describes intent, ownership, and operational expectations and must change with the implementation.

## Current Readiness

The claim-to-invoice vertical workflow is implemented and tested with deterministic mock submission. Atlas is not yet declared production SaaS or enterprise-ready. Pilot blockers and measurable release criteria are tracked in [the release plan](docs/release-plan.md).
