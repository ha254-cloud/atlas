# DHA/SHA eClaims Exchange

## Current Status

Atlas implements a real outbound HTTPS/FHIR transport for:

- OAuth 2.0 client-credentials authentication
- DHA/SHA claim `Bundle` submission
- `ClaimResponse` retrieval
- Structured `OperationOutcome` failures
- Tenant-scoped idempotency, audit, correlation, and append-only exchange events

Atlas is **not DHA-certified**, has not completed HIE UAT, and does not claim a
production SHA connection. The pinned implementation guide is the draft Kenya
eClaims guide version `0.1.0`.

A representative synthetic claim Bundle validates with zero errors against the
official HL7 Validator CLI 7.0.3 and the DHA package
`ke.fhir.eclaims#0.1.0`. The validator reports eight `dom-6` best-practice
warnings because generated narrative XHTML is intentionally omitted; these are
warnings, not conformance errors.

## Configuration

Create an integration with provider `sha`.

Required settings:

```json
{
  "base_url": "https://hie-test.dha.go.ke/fhir",
  "token_url": "https://<DHA-issued-token-host>/oauth/token",
  "client_id": "<DHA-issued-client-id>",
  "provider_number": "<certified-facility-provider-number>",
  "facility_name": "<certified-facility-name>",
  "scopes": "system/Claim.write system/ClaimResponse.read system/Coverage.read",
  "token_auth_method": "client_secret_basic"
}
```

The client secret must use the typed encrypted credential field:

```json
{
  "kind": "oauth2_client_credentials",
  "client_secret": "<DHA-issued-secret>"
}
```

Both the token and FHIR URLs must be absolute HTTPS URLs. Embedded URL
credentials, insecure HTTP, redirects, API-key-only authentication, missing
credentials, and unsupported token authentication methods fail closed.

## API

Human-initiated submission:

```text
POST /api/v1/eclaims/claims/{claim_id}/submit
```

The request identifies the configured SHA integration, reason, idempotency key,
patient SHA or national identifier, required patient and next-of-kin contact
details, treating practitioner identity, invoice and patient-share details,
coverage and annual-limit category, encounter, ICD-11 mappings, and SHA
intervention mappings. Mappings must cover every diagnosis and claim line exactly
once. Only a tenant-owned KES claim assigned to payer code `SHA` is accepted.

Status and evidence:

```text
GET  /api/v1/eclaims/claims/{claim_id}/exchanges
GET  /api/v1/eclaims/exchanges/{exchange_id}
POST /api/v1/eclaims/exchanges/{exchange_id}/refresh
```

Submission and refresh require `submit_claims`; reads require `view_claims`.
Tenant identity always comes from authenticated context.

## FHIR Mapping

The bundle uses `type=collection`, includes `Bundle.meta.lastUpdated`, and places
the claim first. It includes:

- `Claim` using `ke-eclaims-claimsubmission`
- `Patient` using `ke-eclaims-patient`
- `Coverage` using `ke-eclaims-coverage`
- Provider and SHA `Organization` resources
- Treating `Practitioner`
- `Encounter`
- One `Condition` per mapped diagnosis

Atlas transmits ICD-11 and SHA intervention codes supplied through the governed
submission request. Existing CPT/ICD-10 values are not silently relabeled as
Kenya terminology. Required invoice, annual-limit category, patient contact, and
condition-recorder elements are populated from explicit submission data rather
than synthetic defaults.

## Evidence and Privacy

Atlas persists:

- organization, claim, integration, and actor references
- reason, correlation ID, idempotency key, and timestamps
- implementation-guide version
- canonical bundle and response SHA-256 hashes
- HTTP result and external ClaimResponse reference
- adjudication outcome, workflow state, approved amount, currency, and bounded notes
- append-only status/failure events

Full FHIR payloads, OAuth tokens, and patient identifiers are not copied into
ordinary audit metadata or logs.

## Failure Behavior

- OAuth and network failures return a controlled integration error.
- FHIR `OperationOutcome` errors return HTTP 502 from Atlas and record a
  PHI-minimized failure event.
- A failed status check does not rewrite a previously accepted submission as
  failed.
- Reusing an idempotency key for another claim or integration is rejected.
- An accepted response without a retrievable reference is recorded as failed
  rather than represented as success.

## Deployment and Rollback

1. Apply migration `e8c3f1a9d6b2`.
2. Configure the integration encryption key through the production secret store.
3. Add DHA-issued UAT settings and encrypted credentials.
4. Run the live health check and official FHIR validator evidence.
5. Complete HIE UAT and DHA certification before production traffic.

To stop traffic, disconnect the SHA integration. The migration is additive and
backward compatible. Downgrade drops SHA exchange evidence, so retain required
regulatory records before rollback.

## Remaining Certification Work

- Repeat validator evidence against the final DHA certification package
- DHA test-patient sandbox transactions
- HIE UAT claim and response evidence
- DHA certification review and production credentials
- PaymentNotice ingestion
- Eligibility and patient `$match`
- Preauthorization
- Correction and resubmission
- Named hospital acceptance and operational support ownership
