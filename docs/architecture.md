# Atlas Architecture

## Overview

Atlas is a Kenya-first, multi-tenant AI Revenue Recovery Platform. Atlas ingests
claims and remittance data from hospital and payer systems; it does not replace
those systems. A shared Atlas
environment serves many independent healthcare organizations while preserving
complete data, configuration, workflow, integration, reporting, and billing
boundaries.

## System Layers

```
Browser (Next.js 15)
        │
        ▼
Atlas API (FastAPI)
        │
   ┌────┴────┐
   │         │
PostgreSQL  Redis
            │
            ▼
       Celery Workers
```

## Backend Module Structure

```
apps/api/app/
├── api/v1/          — HTTP routing layer (thin controllers only)
├── canonical/       — Internal data models (CDM) all sources map into
├── claims/          — Claims domain (service, repository, router, schemas)
├── dashboard/       — Dashboard aggregation (repository, service, router, analytics)
├── integrations/    — EHR + clearinghouse connectors (base, registry, manager)
│   └── connectors/  — Epic, Athena, Cerner, eCW, Waystar, Availity, Change
├── payers/           — Tenant payer registry, capabilities, and connector routing
├── mcp/             — MCP server (tools, registry, auth, server)
├── models/          — SQLAlchemy ORM models
├── processing/      — Import pipeline (processor, persistence, pipeline)
├── recovery/        — Recovery engine (engine, scorer, rules, calculator, router)
├── workflow_engine/ — Versioned configurable graph executor and API contracts
├── workflows/       — Durable event inbox, trigger matching, action registry
├── ai/              — AI layer (engine, claim analyzer, appeal generator)
├── audit/           — Audit logging (service, actions)
├── core/            — Cross-cutting (config, dependencies, repository base)
├── security/        — JWT, hashing, auth dependencies
└── workers/         — Celery tasks
```

## Multi-Tenancy

`Organization` is the tenant security boundary. Tables are explicitly global,
directly tenant-owned, or parent-scoped. Directly tenant-owned records have a
non-null organization foreign key; child records may inherit scope only through
a documented non-null parent relationship. Tenant identity is never trusted from
client input.

The current schema uses internal integer organization keys. Public UUID adoption
and any foreign-key conversion are staged compatibility migrations; isolation is
enforced by authenticated context, scoped queries, database constraints, and
negative cross-tenant tests. See [Tenant Architecture](tenant-architecture.md)
and [ADR 0001](adr/0001-multi-tenant-saas-boundary.md).

Organization-specific AI policy, fee schedules, feature entitlements, connector
defaults, locale, and workflow behavior belong in typed, versioned tenant
configuration. They must not require code forks.

Hospital groups remain one tenant where their governance requires consolidated
operations. Branch and department are subordinate authorization and reporting
scopes, not replacement tenant boundaries. Country and payer policy extend the
shared platform through versioned configuration and typed modules. See
[ADR 0003](adr/0003-kenya-first-revenue-recovery-platform.md).

Recovery accounting and Atlas customer subscription billing are separate
bounded contexts. Existing recovery invoices do not represent SaaS subscription
invoices.

Atlas's Revenue Recovery Partner model additionally separates prevention value,
hospital recovered cash, attributable net recovery, and Atlas fees. Payment timing
alone never establishes attribution. See
[ADR 0004](adr/0004-revenue-recovery-partner-operating-model.md).

## Configurable Workflows

Domain events are assigned stable event and correlation IDs, persisted to the
tenant-owned workflow inbox, and processed asynchronously by Celery. Active
definitions are matched within the same organization, trigger conditions are
evaluated against event and claim context, and executions are idempotent per
workflow and event. See [Workflow Engine 2.0](workflow-engine-2.0.md) and
[ADR 0002](adr/0002-human-approval-before-appeal-submission.md).

## Data Flow

```
Hospital source (CSV first; SFTP / FHIR / API as available)
         │
         ▼
   CSVNormalizer / FHIRNormalizer / X12Normalizer
         │
         ▼
   CanonicalClaim
         │
         ▼
   ClaimProcessor.process_canonical()
         │
    ┌────┴────┐
    │         │
  Claim    RecoveryCase
    │
    ▼
  analyze_claim_task (Celery)
    │
    ▼
  AIAnalysis
```

Submission, status, and payment workflows resolve through the claim's tenant-owned
payer configuration. A payer may use API, SFTP, email, portal, or manual handling;
Atlas must not imply automated connectivity where only a human workflow exists.
Payments from CSV, Excel, portal exports, emailed reports, and manual entry converge
on the canonical payment and recovery-attribution engine.
