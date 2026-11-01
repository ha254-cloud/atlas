# ADR 0007: DHA/SHA eClaims Exchange Boundary

- Status: Accepted
- Date: 2026-11-01
- Owners: Product, integration engineering, security/privacy, and revenue operations
- Review date: On DHA implementation-guide revision or before production onboarding
- Related milestone: M1

## Context

Kenya's DHA eClaims implementation guide defines a FHIR R4 exchange between a
healthcare provider system, the Kenya HIE, and SHA. Atlas must submit structured
claim bundles, retrieve adjudication responses, preserve human initiation, and
retain defensible evidence without duplicating the shared claim, patient, payer,
payment, or organization domains.

The published guide is draft version `0.1.0`. It requires OAuth 2.0 client
credentials or DHA-issued mutual TLS, HTTPS, Kenya-specific profiles and
terminology, globally unique claim identifiers, duplicate detection, and
auditable transactions. Atlas does not yet hold DHA certification or production
credentials.

## Decision

1. `eclaims/` owns the SHA exchange lifecycle and immutable exchange events.
   Shared clinical and financial facts remain owned by existing Atlas modules.
2. `SHAConnector` is a registered integration plugin. It performs real HTTPS FHIR
   calls and OAuth 2.0 client-credentials authentication. It has no sandbox or
   success-shaped fallback.
3. SHA is an outbound claims exchange, not a pull-sync source. Generic integration
   sync is rejected for this connector.
4. Every submission is explicitly initiated by a user with `submit_claims`
   permission and includes a reason and idempotency key.
5. Atlas constructs the FHIR bundle from the tenant-owned claim plus explicit
   Kenya coding and coverage input. Clients cannot submit arbitrary raw FHIR.
6. Atlas stores request and response hashes, external references, protocol
   version, HTTP outcome, actor, tenant, correlation ID, timestamps, and a
   PHI-minimized response summary. Full request/response bodies are not copied
   into audit records or logs.
7. The connector pins implementation-guide version `0.1.0`. A guide upgrade
   requires mapping review, validator evidence, migration assessment, and this
   ADR's review.
8. "Implemented", "UAT-tested", "DHA-certified", and "production-connected" are
   separate states. The product must not show a certification claim until DHA
   issues evidence for the deployed Atlas version.

## Alternatives Considered

- Extending the appeal submission connector was rejected because primary claim
  exchange, adjudication, eligibility, and payment notices are a different
  protocol and lifecycle.
- Accepting caller-provided FHIR JSON was rejected because it bypasses Atlas
  domain validation, tenant ownership, and data-minimization controls.
- Waiting for production credentials before implementing was rejected because
  the published protocol is sufficient to build and validate the transport,
  persistence, and authorization boundary.
- A simulator was rejected as product transport. HTTP fakes remain permissible
  only inside automated tests.

## Consequences

- Migration `e8c3f1a9d6b2` adds tenant-scoped exchange and append-only event
  tables. It does not alter existing claim or payment contracts.
- OAuth client secrets use the existing encrypted integration credential store.
- Submission remains unavailable until an organization configures DHA-issued
  HTTPS endpoints, client ID, encrypted client secret, provider number, and
  certified facility name.
- PaymentNotice ingestion, eligibility, patient matching, preauthorization, and
  correction/resubmission remain subsequent protocol slices.
- Rollback disables or disconnects the SHA integration, stops new submissions,
  and downgrades the additive migration only after retaining required exchange
  evidence externally.

## Validation

- Validate generated resources with the official HL7 validator and
  `ke.fhir.eclaims#0.1.0`.
- Prove OAuth token exchange, TLS-only URL enforcement, FHIR media types,
  OperationOutcome handling, timeouts, and no redirect following.
- Prove tenant isolation, narrow RBAC, idempotency, append-only events, audit
  before/after evidence, and durable post-commit domain events.
- Complete DHA sandbox, HIE UAT, certification review, and production onboarding
  before changing release readiness.

## Intentional Debt

PaymentNotice receipt, eligibility, patient matching, preauthorization, and
correction/resubmission are not part of the first transport slice. Risk:
bidirectional SHA workflow is incomplete. Mitigation: product copy states the
implemented scope; no certification claim is made; exchange contracts remain
versioned. Owner: integration engineering. Removal condition: DHA UAT onboarding
and the M1 real-payer certification gate. Target: M1 pilot.
