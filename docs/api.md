# Atlas API Reference

Base URL: `https://api.yourdomain.com/api/v1`

All endpoints (except `/auth/login` and `/auth/register`) require:
```
Authorization: Bearer <access_token>
```

## Workflow Engine 2.0

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `/workflows` | List or create tenant workflow definitions |
| PUT, DELETE | `/workflows/{id}` | Update or delete an unused definition |
| POST | `/workflows/{id}/enable` | Enable a definition |
| POST | `/workflows/{id}/disable` | Disable a definition |
| GET | `/workflow-actions` | List registered executable actions |
| GET | `/workflow-history` | List tenant-scoped execution history |
| POST | `/workflow-executions/{id}/approve` | Record a human approval decision |

Definitions with execution history cannot be deleted. Approval resumes the
graph but never submits an appeal. Existing `/workflow-definitions` routes
remain compatible. See [Workflow Engine 2.0](workflow-engine-2.0.md).

## Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login, receive JWT |
| GET | `/auth/me` | Current user profile |

## Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard` | Full dashboard response (metrics + trends + recent) |
| GET | `/dashboard/analytics/denials` | Denial breakdown by type |
| GET | `/dashboard/analytics/recovery-by-payer` | Recovery grouped by payer |
| GET | `/dashboard/analytics/recovery-rate` | Overall collection rate |

## Claims

| Method | Path | Description |
|--------|------|-------------|
| GET | `/claims/` | List claims (paginated) |
| GET | `/claims/export.csv?reason=...` | Export tenant claims in canonical CSV form; requires `export_claims` permission and records audit evidence |
| POST | `/claims/` | Create a claim |
| GET | `/claims/{id}` | Get claim detail |
| PATCH | `/claims/{id}` | Update claim |
| DELETE | `/claims/{id}` | Delete claim |
| GET | `/claims/{id}/timeline` | Immutable event history |

Claim exports contain canonical portability fields rather than internal IDs. Export
access is restricted to owners, administrators, and managers; a reason is mandatory,
the action is correlated in the immutable audit log, and spreadsheet formulas in
text fields are neutralized. Failed or partial integration runs can be re-fetched
through `POST /integrations/{integration_id}/runs/{run_id}/retry`; successful and
running records cannot be replayed through that operation.

## Branches

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `/branches` | List accessible branches or create a tenant branch |
| PATCH | `/branches/{branch_id}` | Rename or activate/deactivate a tenant branch |
| GET, POST | `/branches/{branch_id}/departments` | List or create parent-scoped departments |
| GET, POST | `/branches/{branch_id}/memberships` | List or assign tenant-scoped user memberships |

Owners and administrators manage branch configuration. Managers retain organization
rollup visibility; operational roles see only branches with active memberships.
Claims snapshot branch, optional department, and ISO currency. Composite database
constraints reject cross-organization branch, department, membership, and claim links.

## Payer Intelligence

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `/payers/{payer_id}/profile` | Read or append a tenant payer-profile version |
| GET, POST | `/payers/{payer_id}/contracts` | List or append effective-dated contract tariffs |
| GET, POST | `/payers/{payer_id}/rules` | List or append sourced payer-rule versions |
| GET | `/payers/{payer_id}/claims/{claim_id}/validation` | Run advisory contract and payer-rule checks |
| GET | `/payers/{payer_id}/intelligence` | Read tenant-only payer outcome intelligence |

The intelligence endpoint accepts `minimum_sample_size` (5-1000, default 10).
Recommendations are suppressed below the selected sample threshold. No endpoint
aggregates across hospitals. See [Payer Intelligence Engine](payer-intelligence.md).

## Recovery

| Method | Path | Description |
|--------|------|-------------|
| GET | `/recovery` | Filtered work queue (status, payer, priority, search) |
| PATCH | `/recovery/{id}/status` | Update recovery case status |
| POST | `/recovery/lifecycle/claims/{claim_id}` | Open and synchronize a claim lifecycle account |
| GET | `/recovery/lifecycle/accounts/{account_id}` | Read financial position, recommendation, and event ledger |
| POST | `/recovery/lifecycle/accounts/{account_id}/transitions` | Apply an idempotent state transition |
| POST | `/recovery/lifecycle/accounts/{account_id}/allocations` | Record a contract adjustment or approved write-off |
| POST | `/recovery/lifecycle/accounts/{account_id}/assignment` | Assign lifecycle work with optimistic versioning |
| GET | `/recovery/lifecycle/portfolio` | Read executive recovery and ROI projections |
| GET | `/recovery/lifecycle/forecast` | Read probability-weighted weekly cash forecast |
| GET | `/recovery/lifecycle/billing-readiness` | Read verified, uninvoiced recovery evidence |

All lifecycle routes derive organization scope from authentication. Financial
positions are projections over claims, verified recoveries, and immutable
lifecycle events. The billing-readiness route does not create invoices or alter
fee eligibility. See [Revenue Recovery Lifecycle Engine](revenue-recovery-lifecycle.md).

## MCP

| Method | Path | Description |
|--------|------|-------------|
| GET | `/mcp/tools` | List available tools |
| POST | `/mcp/tools/analyze_claim` | Analyze a claim |
| POST | `/mcp/tools/estimate_recovery` | Estimate recovery |
| POST | `/mcp/tools/generate_appeal` | Generate appeal letter |
| POST | `/mcp/tools/classify_denial` | Classify denial reason |
| POST | `/mcp/tools/check_status` | Check claim status |
| POST | `/mcp/tools/sync_claims` | Sync from EHR |
| POST | `/mcp/tools/reconcile_payment` | Apply a payment |
| POST | `/mcp/keys` | Create MCP API key |
| GET | `/mcp/keys` | List API keys |
| DELETE | `/mcp/keys/{id}` | Revoke API key |

## Notifications

| Method | Path | Description |
|--------|------|-------------|
| GET | `/notifications/stream` | SSE stream for real-time events |
