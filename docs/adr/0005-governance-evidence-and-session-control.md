# ADR 0005: Governance Evidence and Session Control

- Status: Accepted
- Date: 2026-08-03
- Owners: Engineering, Security/Privacy, Operations
- Review date: 2026-11-03
- Related milestone: M1/M2/M3

## Context

Atlas processes healthcare identity, claims, documents, AI recommendations, approvals,
and payments. Hospital auditors need immutable, tenant-scoped evidence and immediate
access revocation. Existing audit rows recorded action/entity metadata but lacked
correlation, change state, reason, and database-enforced immutability. JWTs could not be
revoked before expiry. Consent and retention policy records did not exist.

## Decision

The Governance module owns the canonical audit writer, patient consent versions,
retention policy versions, revocable sessions, and compliance projections.

- Extend the existing `audit_logs` table rather than create a competing event store.
- Reject audit updates/deletes with database triggers.
- Derive request correlation/device evidence in middleware and inherit it through a
  context-local audit boundary.
- Store consent and retention changes as append-only versions.
- Add a server-side session ID to newly minted JWTs and validate it on every request.
- Keep retention enforcement report-only until legal hold, archive, and restore
  controls are implemented.

## Alternatives Considered

- A second governance event ledger was rejected because it would split evidence from
  the 36 existing audit call sites.
- Stateless JWT revocation lists were rejected because durable session records also
  support administrator visibility and termination evidence.
- Immediate automated deletion was rejected because Atlas lacks resource-specific
  legal-hold and archive/restore contracts.
- A nullable unverified `branch_id` was rejected until governed branch ownership exists.

## Consequences

New logins create a database session row and incur one session lookup per authenticated
request. Audit rows become operationally append-only; rollback must explicitly remove
the trigger. Existing tokens without `sid` expire through the prior bounded JWT window.
Production database roles and external audit/backup controls remain necessary because
database owners can alter schema-level controls.

## Validation

- API tests for consent/retention versioning, RBAC, redaction, correlation, and sessions.
- Negative cross-tenant tests for audit, consent, retention, and session records.
- Raw SQL update/delete rejection tests.
- PostgreSQL migration upgrade/downgrade/re-upgrade rehearsal.
- Web type-check, production build, and responsive browser checks.

## Intentional Debt

Automatic retention enforcement is deferred because legal hold and verified archive
restore do not exist. Security/Privacy and Operations own removal of this debt before
production healthcare data onboarding. Review at the M1 pilot security gate and no
later than 2026-11-03.