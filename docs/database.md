# Atlas Database Schema

## Tables

### Core
- `organizations` — tenants
- `users` — user accounts (role: admin/biller/auditor/viewer)
- `api_keys` — MCP API keys (hashed, never plaintext)
- `integrations` — EHR/clearinghouse integration config (tokens encrypted with Fernet)

### Claims Domain
- `patients` — patient records
- `payers` — insurance payers
- `payer_policy_sources` — directly tenant-owned, immutable, effective-dated,
  maker/checker-approved Kenya policy-source versions bound to a same-tenant payer
- `claims` — individual claims
- `claim_lines` — line items within a claim
- `claim_events` — immutable event timeline per claim
- `denials` — denial records attached to claims

### Recovery
- `recovery_cases` — recovery opportunities with score + priority
- `ai_analyses` — AI analysis results per claim

### Operations
- `import_jobs` — background import job tracking
- `audit_logs` — system-wide immutable audit trail

### Appeal Grounding

`appeals.grounding_report` stores JSON provenance for the policy sources selected
at generation time: source ID, policy code, version, source reference, effective
dates, approval timestamp, content checksum, applicability inputs, and filtered
model-citation counts. It does not copy policy text. The source record remains the
authoritative reviewed content.

## Multi-Tenancy

Directly tenant-owned tables include:
```sql
organization_id INTEGER NOT NULL REFERENCES organizations(id)
```
with an index for tenant-scoped queries. Parent-scoped child tables may inherit
ownership through a non-null foreign key to a tenant-owned aggregate. Global
tables require an explicit documented classification.

The current internal key type is `INTEGER`. Atlas will add UUID public organization
identifiers before changing external contracts; an integer-to-UUID foreign-key
rewrite, if required, is a separate staged migration. UUIDs reduce enumeration
but do not replace authenticated tenant scoping.

The authoritative table classification is checked by
`apps/api/tests/test_tenant_model_contract.py`; see
[Tenant Architecture](tenant-architecture.md).

## Migrations

```bash
# Generate a new migration
cd apps/api && alembic revision --autogenerate -m "description"

# Apply all pending migrations
cd apps/api && alembic upgrade head

# Rollback one migration
cd apps/api && alembic downgrade -1
```
