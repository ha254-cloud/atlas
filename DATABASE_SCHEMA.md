# Atlas Database Schema

Last verified: 2026-10-29
Alembic head: `d4f7a2c6e9b3`
Registered SQLAlchemy tables: 76

This file is the admission registry for physical database tables. SQLAlchemy models
and Alembic migrations remain the executable definitions of columns, constraints,
indexes, and upgrade/rollback behavior. A migration that adds or renames a table must
update this registry in the same change and pass the architecture contract tests.

## Change Gate

Before changing the physical schema:

1. Confirm the canonical owner in `docs/module-registry.md`.
2. Search this registry, ORM metadata, and every Alembic revision for an existing owner.
3. Prefer extending an existing aggregate over creating another table.
4. Classify the table as global, directly tenant-owned, or parent-scoped.
5. Define foreign keys, uniqueness, indexes, retention, audit, migration, rollback,
   and cross-tenant tests.
6. Update this file, the model, migration, tests, and `BUILD_STATUS.md` together.

Names from planning documents are business vocabulary, not permission to duplicate
implemented tables. For example, `claim_lines` owns claim items, `appeal_submissions`
owns submission logs/state, `invoices` owns hospital recovery invoices, and payment
matching provenance currently belongs to `payments`. Renaming or splitting these
requires an approved migration with a demonstrated semantic need.

## Tenancy Classes

- **Global**: platform root/reference data with explicitly reviewed global access.
- **Direct**: non-null `organization_id`; every query is tenant-scoped.
- **Parent**: ownership is enforced through a non-null foreign key to a tenant-owned
  parent. Some parent-scoped tables also carry `organization_id` for defense in depth.

## Ownership Summary

| Owner | Tables | Tenancy notes |
|---|---:|---|
| Organizations | 2 | `organizations` is the platform root; settings are organization-scoped versions. |
| Branches and departments | 3 | Branches are directly tenant-owned; departments and memberships enforce branch/organization consistency through composite foreign keys and also carry a direct organization_id -> organizations.id foreign key for defense in depth. |
| Users and security | 5 | Users, invitations, API keys, and user-owned credential tokens. |
| Patients and governance | 4 | Patient identity, consent versions, retention policies, and sessions. |
| Claims, denials, and imports | 11 | Claims plus lines, diagnoses, validation, events, decisions, analyses, workflows, denials, and import jobs. |
| Documents | 3 | Claim-parented evidence records, immutable versions, and append-only holds. |
| Payers | 3 | Tenant payer registry, policy sources, and statistics. |
| Appeals and submissions | 4 | Appeals and immutable versions; human-triggered submissions and events. |
| Payments, recovery, and billing | 16 | Canonical payments, immutable settlement/allocation/intervention/attribution/dispute evidence, operational recovery projections, fee schedules, recovery invoices, credit notes, and reconciliation runs. |
| AI and Copilot | 6 | Tenant-attributed AI usage/execution and Copilot conversations/messages/confirmations. |
| Tasks and notifications | 4 | Tasks, activities, skills, and durable task notifications. |
| Workflows | 5 | Definitions, steps, executions, step executions, and durable event inbox. |
| Integrations and webhooks | 8 | Connectors, credential/mapping/sync history, subscriptions, and deliveries. |
| Domain events | 1 | Durable transactional outbox for tenant domain events. |
| Audit | 1 | Immutable tenant audit evidence. |

## Canonical Table Manifest

The following fenced block is machine-checked against `Base.metadata`. Keep one table
name per line in lexical order.

```tables
agent_execution_logs
ai_analyses
ai_call_logs
api_keys
appeal_submission_events
appeal_submissions
appeal_versions
appeals
audit_logs
branch_memberships
branches
claim_analyses
claim_decisions
claim_diagnoses
claim_events
claim_lines
claim_validation_issues
claim_workflows
claims
copilot_confirmations
copilot_conversations
copilot_messages
denial_codes
denials
departments
document_holds
document_versions
documents
domain_event_outbox
email_verification_tokens
import_jobs
integration_credential_versions
integration_mapping_fields
integration_mapping_profiles
integration_sync_errors
integration_sync_runs
integrations
invitations
invoice_credit_notes
invoice_lines
invoice_reconciliation_runs
invoices
organization_settings_versions
organizations
password_reset_tokens
patient_consents
patients
payer_policy_sources
payer_statistics
payers
payment_allocations
payment_settlement_evidence
payments
recoveries
recovery_accounts
recovery_attribution_dispute_resolutions
recovery_attribution_disputes
recovery_attribution_versions
recovery_cases
recovery_fee_schedules
recovery_interventions
recovery_lifecycle_events
retention_policies
task_activities
task_notifications
tasks
user_sessions
user_task_skills
users
webhook_delivery_logs
webhook_subscriptions
workflow_definitions
workflow_events
workflow_executions
workflow_step_executions
workflow_steps
```

## Table Ownership And Scope

### Global

| Table | Canonical owner | Model source |
|---|---|---|
| `organizations` | Organizations | `app/organizations/models.py` |
| `denial_codes` | Denials and knowledge | `app/models/denial_code.py` |

### Tables Carrying Organization ID

These 63 tables carry non-null `organization_id`: `agent_execution_logs`, `ai_analyses`,
`ai_call_logs`, `api_keys`, `appeal_submission_events`, `appeal_submissions`,
`appeal_versions`, `appeals`, `audit_logs`, `branch_memberships`, `branches`,
`claim_analyses`, `claim_decisions`,
`claim_events`, `claim_validation_issues`, `claim_workflows`, `claims`,
`copilot_confirmations`, `copilot_conversations`, `copilot_messages`, `denials`,
`departments`, `document_holds`, `document_versions`, `documents`,
`domain_event_outbox`, `import_jobs`,
`integration_mapping_profiles`, `integration_sync_runs`,
`integrations`, `invitations`, `invoice_reconciliation_runs`, `invoices`,
`organization_settings_versions`,
`patient_consents`, `patients`, `payer_policy_sources`, `payer_statistics`, `payers`,
`payment_allocations`,
`payment_settlement_evidence`, `payments`, `invoice_credit_notes`,
`recoveries`, `recovery_accounts`, `recovery_attribution_dispute_resolutions`,
`recovery_attribution_disputes`, `recovery_attribution_versions`,
`recovery_cases`, `recovery_fee_schedules`, `recovery_interventions`,
`recovery_lifecycle_events`,
`retention_policies`, `task_activities`, `task_notifications`, `tasks`,
`user_sessions`, `user_task_skills`, `users`, `webhook_subscriptions`,
`workflow_definitions`, `workflow_events`, and `workflow_executions`.

The physical tenant key does not replace parent validation where both keys exist.
Semantically, root aggregates are directly tenant-owned while child/history tables
remain parent-scoped with an additional organization key for defense in depth. Services
must prove that referenced parents belong to the same organization.

`payment_settlement_evidence` and `payment_allocations` are directly tenant-owned,
append-only ledgers. PostgreSQL `ENABLE ALWAYS` triggers and SQLite test triggers
reject update/delete. Reversals and refunds are positive compensating allocation
rows linked by `parent_allocation_id`; current balances are projections, not mutable
ledger totals. `invoice_credit_notes` is directly tenant-owned and immutable; each
invoiced allocation adjustment can issue at most one credit note. `recoveries` now
allows one projection per `(payment_id, claim_id)` so a payment can be split across
claims while preserving the legacy single-claim path.

`recovery_interventions`, `recovery_attribution_versions`,
`recovery_attribution_disputes`, and
`recovery_attribution_dispute_resolutions` are directly tenant-owned append-only
financial evidence. Each attribution version snapshots the effective commercial
terms and links its predecessor; disputes and resolutions never overwrite a prior
decision. `invoice_reconciliation_runs` is directly tenant-owned and immutable,
preserving each independent exact-money recomputation. Credit notes now have exactly
one immutable source: either a payment-allocation adjustment or an attribution
dispute resolution.

### Parent-Scoped Without Organization ID

These 11 tables are queried only through their tenant-owned parent boundary.

| Table | Owning parent boundary | Canonical owner |
|---|---|---|
| `claim_diagnoses` | `claim_id -> claims` | Claims |
| `claim_lines` | `claim_id -> claims` | Claims |
| `email_verification_tokens` | `user_id -> users` | Authentication |
| `integration_credential_versions` | `integration_id -> integrations` | Integrations |
| `integration_mapping_fields` | `profile_id -> integration_mapping_profiles` | Integrations |
| `integration_sync_errors` | `sync_run_id -> integration_sync_runs` | Integrations |
| `invoice_lines` | `invoice_id -> invoices` | Invoices |
| `password_reset_tokens` | `user_id -> users` | Authentication |
| `webhook_delivery_logs` | `subscription_id -> webhook_subscriptions` | Webhooks |
| `workflow_step_executions` | execution and step parents | Workflow engine |
| `workflow_steps` | `workflow_id -> workflow_definitions` | Workflow engine |

## Planned Schema Work

Planned tables are not admitted tables and must not appear in the canonical manifest
until their migration is implemented and verified.

| Batch | Planned capability | Constraint |
|---|---|---|
| One | Patient and document completion | Reuse `patients` and `documents`; add a table only for proven version/history semantics that cannot be represented safely. |
| Foundation blocker | Branches, departments, memberships, claim branch snapshots | Requires the ADR 0003 tenant and authorization design before migration. |
| Four | Atlas SaaS subscriptions and customer invoices | Must remain separate from hospital recovery `invoices` and recovery fee schedules. |

## Verification

`apps/api/tests/test_architecture_contracts.py` compares this manifest with imported
SQLAlchemy metadata. Alembic must have exactly one head, and PostgreSQL upgrade plus
rollback/reapply rehearsal remains required for every schema change.