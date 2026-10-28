# Atlas Engineering Principles

## Purpose

Atlas handles healthcare, identity, financial, and operational data. Engineering decisions must remain defensible under hospital security review, insurer dispute, regulatory inquiry, financial diligence, and long-term maintenance.

These principles are requirements. Exceptions require an Architecture Decision Record (ADR) with an owner, rationale, risk, mitigation, and removal or review date.

## 1. Complete Modules

A domain module is not complete until it has the applicable layers:

- Models and migrations
- Input/output schemas
- Tenant-scoped repository
- Business service
- API and/or event entrypoint
- Unit, integration, authorization, and failure-path tests
- Operator and developer documentation
- Audit and observability behavior

A layer may be marked not applicable only with a documented reason.

## 2. Event-Driven Boundaries

Events are facts that have already committed. Event names use past tense and stable domain vocabulary, for example `claim.imported`, `appeal.approved`, and `submission.paid`.

- Publish only after durable state commits.
- Include `event_id`, `event_version`, `occurred_at`, `organization_id`, `correlation_id`, actor identity when known, and entity references.
- Consumers must be idempotent and tolerate duplicate or out-of-order delivery.
- Never use an event when an immediate response or one atomic transaction is required.
- Cross-domain synchronous calls require a short rationale in code or an ADR.

The target recovery stream is:

```text
claim.created -> claim.imported -> claim.analyzed -> appeal.generated
-> appeal.approved -> submission.created -> submission.completed
-> payment.posted -> recovery.verified -> invoice.generated
```

## 3. Plugin Architecture

Vendor integrations implement registered interfaces. Core domain services depend on connector contracts, never vendor SDKs.

Each connector must define:

- Typed configuration and secret requirements
- Authentication and health behavior
- Timeouts, retries, and idempotency
- Canonical request/response mapping
- Error taxonomy
- Contract tests and a mock implementation
- Operational runbook

A connector is not production-ready because its class exists. Stub, sandbox, pilot, and production are distinct documented states.

## 4. Replaceable AI

`AIGateway` is the only provider-aware boundary. Domain code supplies a task, versioned prompt, structured schema, and tenant context.

Store provider, model, prompt version, latency, token/cost data, validation outcome, correlation ID, and resulting artifact version. AI output is advisory until the owning workflow explicitly accepts it.

## 5. Immutable Versions

Appeals, analyses, prompts, policies, rules, and material documents are append-only versions. Corrections create new versions; they do not erase history.

Every version records its predecessor, author or generator, timestamp, reason, and applicable model/policy metadata.

## 6. Auditability

Every material mutation must answer:

- Who initiated it?
- When did it occur?
- What changed before and after?
- Why did it change?
- Which tenant and entity were affected?
- Which request, task, event, or external message caused it?

Audit records are immutable and access-controlled. Sensitive values are redacted rather than copied blindly into metadata.

## 7. Observability

Every request and asynchronous execution must carry a correlation ID. Structured telemetry should include request/task/event ID, organization ID, user ID, duration, status, error class, external-provider latency, and database query metrics.

Logs must never contain passwords, tokens, raw medical documents, or unnecessary protected health information. Production services require health checks, alert ownership, dashboards, and runbooks.

## 8. Security and Tenant Isolation

Every non-public endpoint requires authentication, tenant ownership enforcement, least-privilege RBAC, validated input, and audit treatment appropriate to its risk.

Tenant identity comes from trusted authentication context. Services and repositories enforce tenant scope even when the router already checked it. Secrets belong in a secrets manager and must fail closed when missing in production.

Every persisted table is explicitly global, directly tenant-owned, or
parent-scoped. Every feature must preserve organization context across API,
task, event, AI, integration, report, audit, cache, and storage boundaries. A
feature without negative cross-tenant tests is incomplete.

## 9. Configuration Over Code

Payer rules, fee schedules, workflow thresholds, model/provider choices, polling intervals, timeouts, and feature flags belong in typed configuration or versioned tenant settings.

Configuration changes require validation, audit history, safe defaults, and documented rollback.

An organization must be onboardable without a code change. Tenant differences
use typed, versioned settings and registered plugins, never customer-specific
branches or forks.

## 10. Separate Financial Domains

Hospital revenue recovery accounting and Atlas customer SaaS billing are
separate bounded contexts, ledgers, services, permissions, invoices, and reports.
Recovery attribution must never be treated as subscription metering, and SaaS
payments must never alter hospital recovery records.

## 11. Four Engines

Every capability maps to one primary engine:

- Intelligence: analysis, recommendations, appeals, and Copilot
- Workflow: state transitions, queues, automation, and scheduling
- Integration: APIs, FHIR, X12, SFTP, browser automation, and webhooks
- Revenue: payment matching, attribution, fees, invoices, and financial reporting

Shared platform capabilities include identity, organizations, audit, events, documents, settings, observability, and security.

## Decision Records

Create an ADR from `docs/adr/0000-template.md` for new infrastructure, cross-domain coupling, external protocols, security models, durable schemas, or intentional debt.
