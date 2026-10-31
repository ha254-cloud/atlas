# Payer Intelligence Engine

## Scope

Sprint 20 adds a tenant-scoped payer intelligence foundation to the canonical
`app.payers` module. It does not create a second payer identity and it does not
represent any Kenyan payer rule, tariff, contact, or workflow as verified unless
an authorized hospital user records a source.

Implemented capabilities:

- append-only payer profile versions with preferred documents, contacts, SLA, and notes;
- append-only, effective-dated contract versions with ISO currency and parent-scoped tariffs;
- append-only, effective-dated payer rules with source provenance and conditions;
- advisory claim validation for missing tariffs, tariff mismatches, authorization,
  filing deadlines, referrals, and required documents;
- tenant-only denial, payment-time, appeal-success, recovery, and successful-document aggregates;
- evidence-labeled recommendations suppressed below a configurable sample threshold.

Validation never submits a claim or appeal. AI is not used in this slice. All
recommendations are deterministic summaries of persisted tenant facts and require
human review.

## Governed Appeal Policy Sources

The payer registry also owns immutable `payer_policy_sources` versions for Kenya
appeal grounding. A source records its payer, policy code, source type, reviewed
text, source reference and optional URI, effective dates, denial/procedure scope,
SHA-256 checksum, change reason, and maker/checker approval evidence.

Draft, pending, rejected, retired, expired, future-effective, wrong-payer, and
wrong-tenant versions never enter an appeal prompt. A submitter cannot approve or
reject the same version. Approving a newer version retires the prior approved
version with the same policy code. Atlas does not ship payer policy content as
verified merely because this storage and approval workflow exists.

Appeals persist a `grounding_report` containing the selected source IDs, versions,
effective dates, checksums, applicability inputs, and rejected model-citation
count. Sectioned drafts render policy references deterministically from selected
sources rather than trusting model-written policy prose. If no source applies,
the draft explicitly requires payer-policy verification.

## Ownership And Security

`payer_profile_versions`, `payer_contracts`, and `payer_rules` are directly
tenant-owned through non-null `organization_id`. `payer_contract_tariffs` is
parent-scoped and may only be accessed through a tenant-owned contract. Every
repository lookup begins with the authenticated organization context; clients do
not provide organization IDs.

Configuration writes require `configure_integrations`. Intelligence reads require
`view_analytics`; registry/profile/contract/rule reads and validation require
`view_claims`. Material writes include actor, reason, organization, timestamp,
correlation ID, and immutable version identifiers in the audit log.

Contract and profile data is confidential hospital business information. Logs and
recommendations contain identifiers, counts, categories, and configured document
names, not patient data. Claim validation results are computed on demand and are
not persisted.

## API

| Method | Path | Purpose |
|---|---|---|
| GET, POST | `/payers/{payer_id}/profile` | Read current or append a profile version |
| GET, POST | `/payers/{payer_id}/contracts` | List or append contract versions and tariffs |
| GET, POST | `/payers/{payer_id}/rules` | List or append sourced payer-rule versions |
| GET | `/payers/{payer_id}/claims/{claim_id}/validation` | Run advisory contract and rule checks |
| GET | `/payers/{payer_id}/intelligence` | Read tenant-only aggregate intelligence |
| GET, POST | `/payers/{payer_id}/policy-sources` | List or create immutable policy-source versions |
| POST | `/payers/{payer_id}/policy-sources/{source_id}/submit-for-approval` | Submit a draft/rejected version |
| POST | `/payers/{payer_id}/policy-sources/{source_id}/approve` | Independently approve a version |
| POST | `/payers/{payer_id}/policy-sources/{source_id}/reject` | Independently reject with a reason |

`minimum_sample_size` on the intelligence endpoint defaults to 10 and accepts
values from 5 through 1000. Below the selected threshold Atlas returns facts with
`insufficient` confidence and no recommendations.

## Cross-Hospital Learning

Cross-hospital aggregation is not implemented. A future release must have all of
the following before any endpoint, job, report, cache, or model training path is
enabled:

- explicit opt-in customer agreement and documented purpose limitation;
- privacy, security, legal, and Kenyan data-protection review;
- exclusion of patient, claim, hospital, contract, contact, and free-text identifiers;
- minimum cohort and dominance thresholds with suppression of small cells;
- approved aggregation dimensions and protection against differencing attacks;
- tenant-visible consent withdrawal, deletion, provenance, and audit controls;
- independent re-identification testing and monitored export controls.

A payer name alone does not make an aggregate anonymous. Contract tariffs and rare
procedure/outcome combinations can identify a hospital and must not enter shared
benchmarks without explicit governance.

## Revenue Recovery Marketplace

Marketplace dispatch is intentionally not part of this module. It builds on the
partner commercial and financial controls in ADR 0004. Production use requires
partner authorization, hospital approval per case, least-privilege work queues,
append-only intervention and attribution ledgers, payment allocation, disputes,
reversals, credit notes, and contractual data-processing boundaries. Hospitals
retain custody of cash and Atlas must not infer a success fee from payer status.

## Deployment And Rollback

Migration `b9d4e7f2a6c1` creates the four payer-intelligence tables and can be
downgraded while they are empty or after their data is deliberately exported and
accepted for deletion. The change adds no secrets, workers, schedules, external
calls, caches, or provider dependencies.

Migration `6b8f1e3d9a2c` adds governed policy sources and appeal grounding
provenance. Its PostgreSQL upgrade/downgrade/upgrade cycle has been rehearsed
locally with one Alembic head. Pilot readiness still requires representative
Kenyan design-partner policies, legal/clinical review, alerting, performance
measurement, and workflow acceptance testing.
