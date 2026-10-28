# Governance, Risk, and Compliance

## Scope

Sprint 23 establishes Atlas's governance baseline without replacing the existing
domain audit call sites. `app.governance` owns policy, consent, session, compliance,
and the canonical audit writer. `app.audit.service` remains a compatibility import.

Implemented controls:

- Tenant-scoped audit queries and correlation timelines.
- Request-derived correlation ID, IP address, user agent, and device classification.
- Structured before/after state, reason, and recursive secret redaction.
- PostgreSQL and SQLite triggers rejecting audit updates and deletes.
- Append-only patient consent decisions by purpose and version.
- Append-only retention policy versions in `report_only` enforcement mode.
- JWT sessions with server-side revocation, logout, password-reset revocation, and
  hospital-administrator termination.
- Compliance and security summaries covering audit volume, documentation gaps,
  approvals, inactive users, login failures, sessions, consent, retention, and AI
  prompt/approver evidence.

## Ownership Classification

| Table | Classification | Ownership rule |
|---|---|---|
| `audit_logs` | Directly tenant-owned | Every query filters authenticated `organization_id`. |
| `patient_consents` | Directly tenant-owned | `organization_id` and `patient_id` must agree; service verifies both. |
| `retention_policies` | Directly tenant-owned | Versions are unique per organization and resource type. |
| `user_sessions` | Directly tenant-owned | Session, user, and authenticated organization must agree. |

`branch_id` and department scope are intentionally absent until the governed branch,
department, and membership models in ADR 0003 exist. An unverified integer branch
reference would weaken rather than improve the audit boundary.

## Audit Immutability

Application code has no audit update or delete API. Database triggers reject `UPDATE`
and `DELETE` against `audit_logs`. Migration rollback first removes the trigger, then
removes the added evidence columns.

Database owners can always perform privileged infrastructure operations. Production
tamper resistance therefore also requires restricted database ownership, exported
database audit logs, encrypted backups, and alerting on DDL or trigger changes.

Sensitive keys containing `password`, `token`, `secret`, `authorization`, or `cookie`
are replaced with `[REDACTED]`. Callers must still provide minimal business state and
must not copy raw clinical documents into audit JSON.

## Consent

Consent purposes are `research`, `ai_processing`, `data_sharing`, and `retention`.
Decisions are `granted`, `denied`, or `revoked`. A change appends the next version and
records actor, reason, timestamp, organization, and correlation ID. Prior decisions
remain queryable.

The consent register records hospital decisions; it does not itself establish lawful
basis or replace hospital consent forms. Atlas Network and cross-hospital aggregation
remain prohibited until privacy, anonymization, cohort-suppression, and governance
controls are approved.

## Retention

Retention policies are versioned and constrained to 1–36,500 days. They remain
`report_only`. Automatic archive/delete is blocked until each resource has:

- a verified archive destination and restore test;
- legal-hold and dispute preservation semantics;
- parent/child deletion ordering and cross-tenant tests;
- a dry-run report, approval workflow, metrics, and operator runbook.

Audit-log retention may archive but must never silently erase evidence required by
law, contract, dispute, or financial policy.

## Sessions

New access tokens contain a `sid` linked to `user_sessions`. Authentication rejects
revoked, expired, mismatched, missing, or inactive-user sessions. Logout and password
reset revoke sessions. Tokens minted before this migration have no `sid` and remain
valid only until their existing configured expiry; this bounded compatibility window
avoids an unannounced forced logout during deployment.

## APIs

- `GET /api/v1/governance/summary`
- `GET /api/v1/governance/audit/correlations/{correlation_id}`
- `POST|GET /api/v1/governance/patients/{patient_id}/consents`
- `POST|GET /api/v1/governance/retention-policies`
- `GET /api/v1/governance/sessions`
- `POST /api/v1/governance/sessions/{session_id}/revoke`
- `POST /api/v1/auth/logout`

Auditors receive read access through `VIEW_GOVERNANCE`. Organization owners and
administrators receive `MANAGE_GOVERNANCE`. No endpoint accepts organization identity
from the request body.

## Remaining Enterprise Controls

- Branch/department models and delegated department administration.
- Configurable role templates and segregation-of-duties approval.
- SSO/SAML/OIDC, SCIM, MFA, geo-enrichment, and anomaly scoring.
- Signed audit exports, evidence packages, external timestamping, and SIEM delivery.
- Resource-specific legal hold, archive, restore, deletion, and subject-access flows.
- Provider-managed scheduled backups, point-in-time recovery, document redundancy,
  and measured disaster-recovery exercises.