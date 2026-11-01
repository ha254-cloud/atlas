# Atlas Integrations

## Architecture

```
Hospital HIS / Payer
           │
           ▼
    BaseConnector (interface)
           │
     ┌─────┴──────┐
     │            │
       HIS         Payer
  Epic          Waystar
  Athena        Availity
  Cerner        Change HC
  eCW
                SHA eClaims
           │
           ▼
    CanonicalClaim / CanonicalPatient / CanonicalPayment
           │
           ▼
    Import Pipeline → Database
```

## Kenya-First Payer Registry

`app.payers` owns each organization's payer registry. A payer records its country,
submission/status/payment methods, portal and endpoint metadata, supported transport
capabilities, and optional registered connector/integration binding. Submission routing
uses the claim's payer before any organization-level fallback. Payer and integration
lookups are always scoped to authenticated organization context.

Manual, email, and portal workflows are first-class configurations. They do not claim
automated transport. Payment reconciliation accepts CSV, Excel, portal exports, emailed
reports, API/SFTP messages, and manual entry through one canonical payment engine.

The DHA/SHA eClaims transport is implemented for OAuth 2.0 client credentials,
FHIR claim Bundle submission, and ClaimResponse retrieval against configured
HTTPS endpoints. A representative synthetic Bundle passes the official HL7
validator against the DHA draft package `ke.fhir.eclaims#0.1.0` with zero errors
and eight narrative best-practice warnings. It is not DHA-certified,
HIE-UAT-tested, or production-connected.
Jubilee, AAR, Britam, and CIC remain discovery and connector-roadmap targets. A
payer connector is only promoted to pilot or production status after protocol
discovery, contractual access, sandbox/contract tests, security review,
operational ownership, certification where required, and pilot evidence.

See `sha-eclaims.md` and ADR 0007 for the exact implemented scope and deployment
gates.

## EHR Connectors (FHIR Sprint)

| Connector | Auth | Protocol | Status |
|-----------|------|----------|--------|
| Epic | SMART on FHIR (OAuth2 + PKCE) | FHIR R4 | Stub |
| Athena | OAuth2 | FHIR R4 + REST | Stub |
| Cerner | SMART on FHIR | FHIR R4 | Stub |
| eClinicalWorks | OAuth2 | FHIR R4 + REST | Stub |

## Clearinghouse Connectors (Clearinghouse Sprint)

| Connector | Auth | Protocol | Status |
|-----------|------|----------|--------|
| Waystar | API Key | X12 EDI (837/835/277) | Stub |
| Availity | OAuth2 | X12 + REST | Stub |
| Change Healthcare | OAuth2 | X12 + REST | Stub |

## Kenya DHA/SHA eClaims

| Connector | Auth | Protocol | Status |
|-----------|------|----------|--------|
| SHA | OAuth 2.0 client credentials | Kenya eClaims FHIR R4, IG 0.1.0 | Implemented and locally validated; certification and UAT open |

SHA is an outbound exchange and intentionally does not implement generic pull
sync. Atlas builds governed FHIR resources from the tenant-owned claim and
explicit Kenya coding inputs; callers cannot send arbitrary raw bundles.

## Scheduled SFTP Claim Feed

SFTP CSV ingestion is implemented for hospital systems that can export claim files but do not expose an API.

- Configure the feed from **Integrations → SFTP**.
- Atlas accepts password or SSH private-key authentication; credentials are encrypted at rest.
- A SHA-256 server host-key fingerprint is required to prevent man-in-the-middle connections.
- Celery Beat checks configured SFTP feeds every four hours; administrators can also select **Sync now**.
- Matching CSV files are normalized and sent through the same validation, patient/payer matching, recovery, timeline, and workflow pipeline as manual uploads.
- Remote files are identified by path, size, and modification time. Atlas records a file as processed only after its claims persist successfully, so failed imports remain retryable.

Required CSV columns:

```text
claim_number,patient_first_name,patient_last_name,payer_code,billed_amount,paid_amount,service_date
```

Recommended optional columns include `medical_record_number`, `status`, `denial_code`, `denial_reason`, `diagnosis_codes`, and `procedure_codes`.

Hospital IT must provide:

1. SFTP hostname and port.
2. Dedicated read-only username and password or private key.
3. Remote inbox path and filename pattern, normally `*.csv`.
4. The server's `SHA256:` host-key fingerprint through a trusted channel.

## Credential Control Plane

Each registered connector declares one typed credential contract:

- Epic, Athena, Cerner, eClinicalWorks, Availity, and Change Healthcare use OAuth2 credentials.
- Waystar uses an API key.
- SFTP uses exactly one password or SSH private key.

Secrets are encrypted in the current `Integration` record and are never returned by the API,
written to audit metadata, or copied into credential history. Every initial configuration and
rotation appends an immutable version containing only the credential kind, non-reversible
SHA-256 fingerprints, expiry, actor, reason, correlation ID, and timestamp.

Credential operations require `configure_integrations` permission and derive the organization
from authenticated context:

- `POST /api/v1/integrations` accepts the typed `credentials` object.
- `POST /api/v1/integrations/{id}/credentials/rotate` replaces the usable secret and requires a reason.
- `GET /api/v1/integrations/{id}/credentials/versions` returns secret-free rotation history.

Expired OAuth2 credentials are rejected before authentication, sync, or health-check calls.
Health checks use `INTEGRATION_HEALTH_TIMEOUT_SECONDS` and
`INTEGRATION_HEALTH_RETRIES`, emit latency metrics and structured correlation logs, and return a
controlled disconnected state after failure. Manual sync request IDs continue into the Celery task
and resulting domain event.

## Adding a New Data Connector

1. Create `app/integrations/connectors/myconnector.py`
2. Inherit from `BaseConnector`
3. Implement: `authenticate`, `sync_claims`, `sync_patients`, `sync_payments`, `health_check`
4. Add the provider's typed credential kind to `PROVIDER_CREDENTIAL_KINDS`.
5. Register in `app/integrations/connectors/__init__.py`; registration fails without a credential contract.
6. Add contract tests for credentials, authentication failure, timeout/retry, canonical mapping, and tenant isolation.
7. Return `CanonicalClaim` objects from `sync_claims` — never raw vendor payloads.

Payer submission connectors implement `PayerConnector` and its appeal submission and
status methods. Claim submission and payment/denial report methods are optional until
the payer's supported protocol is known. Connector contract tests must include tenant
isolation, timeout/error behavior, and evidence that human appeal approval remains
mandatory.

## Canonical Data Model

All connectors map to these internal types before any persistence:

- `CanonicalClaim` — claim_number, payer_code, billed_amount, diagnosis_codes, procedure_codes
- `CanonicalPatient` — first_name, last_name, mrn, date_of_birth
- `CanonicalPayment` — claim_number, paid_amount, payment_date, payer_code
