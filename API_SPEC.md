# Atlas API Specification

Last verified: 2026-10-27  
API version prefix: `/api/v1`  
Registered operations: 228

This file is the admission registry for Atlas HTTP operations. The generated FastAPI
OpenAPI document at `/openapi.json` remains the executable source for request/response
schemas, parameters, status codes, and operation IDs. Any route change must update this
manifest, OpenAPI-facing tests, documentation, and `BUILD_STATUS.md` in the same change.

## Change Gate

Before adding or changing an endpoint:

1. Confirm the canonical owner in `docs/module-registry.md`.
2. Search this manifest and all registered routers for the behavior and path.
3. Extend an existing operation when its contract can safely represent the behavior.
4. Define authentication, narrow RBAC, tenant source, validation, error mapping,
   idempotency, audit, events, pagination/filtering, observability, and compatibility.
5. Add API and cross-tenant tests before moving the operation into this manifest.

Operations are domain-specific. Append-only audit evidence has no update/delete API;
AI actions are commands rather than artificial CRUD; approval never implies appeal
submission. `PATCH` is used for partial updates where already implemented. Trailing
slashes shown below are part of the current registered contract.

## Security Baseline

- `/`, `/health`, and the registration/credential-recovery operations are public by
  explicit design.
- All tenant business operations derive organization context from authenticated user
  or API-key context, never from client-supplied organization IDs.
- Every protected operation requires the narrowest existing permission.
- Material mutations require audit evidence with actor, organization, reason,
  timestamp, before/after state when applicable, and correlation ID.
- OpenAPI availability does not make an unfinished connector or mock transport
  production-ready.

## Canonical Operation Manifest

The following fenced block is machine-checked against `app.openapi()`. Keep one
`METHOD /path` pair per line in lexical path order and method order emitted by OpenAPI.

```http
GET /
GET /api/v1/appeals
POST /api/v1/appeals
GET /api/v1/appeals/claim/{claim_id}
POST /api/v1/appeals/sectioned
GET /api/v1/appeals/{appeal_id}
PATCH /api/v1/appeals/{appeal_id}
PUT /api/v1/appeals/{appeal_id}
DELETE /api/v1/appeals/{appeal_id}
POST /api/v1/appeals/{appeal_id}/approve
GET /api/v1/appeals/{appeal_id}/pdf
GET /api/v1/appeals/{appeal_id}/readiness
POST /api/v1/appeals/{appeal_id}/regenerate
POST /api/v1/appeals/{appeal_id}/reject
POST /api/v1/appeals/{appeal_id}/review
POST /api/v1/appeals/{appeal_id}/submissions
POST /api/v1/appeals/{appeal_id}/submit
GET /api/v1/audit-logs
GET /api/v1/branches
POST /api/v1/branches
PATCH /api/v1/branches/{branch_id}
GET /api/v1/branches/{branch_id}/departments
POST /api/v1/branches/{branch_id}/departments
GET /api/v1/branches/{branch_id}/memberships
POST /api/v1/branches/{branch_id}/memberships
POST /api/v1/auth/forgot-password
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET /api/v1/auth/me
POST /api/v1/auth/register
POST /api/v1/auth/reset-password
POST /api/v1/auth/verify-email
POST /api/v1/claims/
GET /api/v1/claims/
GET /api/v1/claims/export.csv
GET /api/v1/claims/lookups/patients
GET /api/v1/claims/lookups/payers
GET /api/v1/claims/{claim_id}
PATCH /api/v1/claims/{claim_id}
DELETE /api/v1/claims/{claim_id}
POST /api/v1/claims/{claim_id}/agents/analyze
GET /api/v1/claims/{claim_id}/analysis
GET /api/v1/claims/{claim_id}/appeals
POST /api/v1/claims/{claim_id}/appeals
POST /api/v1/claims/{claim_id}/appeals/generate
POST /api/v1/claims/{claim_id}/documents
GET /api/v1/claims/{claim_id}/documents
GET /api/v1/claims/{claim_id}/timeline
POST /api/v1/copilot/chat
POST /api/v1/copilot/confirm
GET /api/v1/copilot/conversations
GET /api/v1/copilot/conversations/{conversation_id}
GET /api/v1/dashboard
GET /api/v1/dashboard/analytics/analyst-performance
GET /api/v1/dashboard/analytics/appeals
GET /api/v1/dashboard/analytics/denials
GET /api/v1/dashboard/analytics/executive-summary
GET /api/v1/dashboard/analytics/financial-kpis
GET /api/v1/dashboard/analytics/forecast
GET /api/v1/dashboard/analytics/insights
GET /api/v1/dashboard/analytics/payer-performance
GET /api/v1/dashboard/analytics/recovery-by-payer
GET /api/v1/dashboard/analytics/recovery-rate
GET /api/v1/dashboard/summary
GET /api/v1/decisions/claims/{claim_id}
POST /api/v1/decisions/claims/{claim_id}/evaluate
POST /api/v1/decisions/evaluate-open
GET /api/v1/decisions/executive-forecast
GET /api/v1/decisions/payer-statistics
POST /api/v1/decisions/payer-statistics/refresh
GET /api/v1/decisions/queue
GET /api/v1/denial-codes
GET /api/v1/denial-codes/{code}
GET /api/v1/documents/{document_id}
PATCH /api/v1/documents/{document_id}
DELETE /api/v1/documents/{document_id}
POST /api/v1/documents/{document_id}/classify
POST /api/v1/documents/{document_id}/classification-review
GET /api/v1/documents/{document_id}/download
POST /api/v1/documents/{document_id}/summarize
GET /api/v1/finance/denial-leakage
GET /api/v1/finance/executive
GET /api/v1/finance/forecast
GET /api/v1/finance/overview
GET /api/v1/finance/payers
GET /api/v1/governance/audit/correlations/{correlation_id}
POST /api/v1/governance/documents/{document_id}/holds
GET /api/v1/governance/documents/{document_id}/holds
POST /api/v1/governance/patients/{patient_id}/consents
GET /api/v1/governance/patients/{patient_id}/consents
GET /api/v1/governance/retention-policies
POST /api/v1/governance/retention-policies
POST /api/v1/governance/retention/documents/dry-run
POST /api/v1/governance/retention/documents/enforce
GET /api/v1/governance/sessions
POST /api/v1/governance/sessions/{session_id}/revoke
GET /api/v1/governance/summary
POST /api/v1/imports
GET /api/v1/imports/{job_id}
GET /api/v1/integrations
POST /api/v1/integrations
GET /api/v1/integrations/providers
GET /api/v1/integrations/{integration_id}
POST /api/v1/integrations/{integration_id}/credentials/rotate
GET /api/v1/integrations/{integration_id}/credentials/versions
POST /api/v1/integrations/{integration_id}/disconnect
GET /api/v1/integrations/{integration_id}/health
POST /api/v1/integrations/{integration_id}/sync
GET /api/v1/invoices
POST /api/v1/invoices/monthly
GET /api/v1/invoices/{invoice_id}
POST /api/v1/invoices/{invoice_id}/paid
GET /api/v1/invoices/{invoice_id}/pdf
POST /api/v1/invoices/{invoice_id}/send
GET /api/v1/mcp/keys
POST /api/v1/mcp/keys
DELETE /api/v1/mcp/keys/{key_id}
GET /api/v1/mcp/tools
POST /api/v1/mcp/tools/analyze_claim
POST /api/v1/mcp/tools/check_status
POST /api/v1/mcp/tools/classify_denial
POST /api/v1/mcp/tools/estimate_recovery
POST /api/v1/mcp/tools/generate_appeal
POST /api/v1/mcp/tools/reconcile_payment
POST /api/v1/mcp/tools/sync_claims
GET /api/v1/notifications/stream
POST /api/v1/onboarding/
GET /api/v1/organizations/current
PATCH /api/v1/organizations/current
GET /api/v1/organizations/current/settings
PUT /api/v1/organizations/current/settings
GET /api/v1/organizations/current/settings/history
GET /api/v1/organizations/{organization_id}
GET /api/v1/patients
POST /api/v1/patients
GET /api/v1/patients/{patient_id}
PUT /api/v1/patients/{patient_id}
GET /api/v1/payer-connectivity/analytics/executive-summary
POST /api/v1/payer-connectivity/appeals/{appeal_id}/submit
GET /api/v1/payer-connectivity/connectors
GET /api/v1/payer-connectivity/submissions
GET /api/v1/payer-connectivity/submissions/{submission_id}
POST /api/v1/payer-connectivity/submissions/{submission_id}/refresh
GET /api/v1/payers
GET /api/v1/payers/{payer_id}
GET /api/v1/payers/{payer_id}/health-check
PATCH /api/v1/payers/{payer_id}
POST /api/v1/payers
POST /api/v1/payers/{payer_id}/approve
POST /api/v1/payers/{payer_id}/reject
POST /api/v1/payers/{payer_id}/submit-for-approval
GET /api/v1/payments
GET /api/v1/payments/claims/{claim_id}/tracking
POST /api/v1/payments
GET /api/v1/payments/fee-schedules
POST /api/v1/payments/fee-schedules
GET /api/v1/payments/records
GET /api/v1/payments/records/{payment_id}
POST /api/v1/payments/records/{payment_id}/match
GET /api/v1/platform-admin/hospitals
GET /api/v1/platform-admin/summary
GET /api/v1/recoveries
POST /api/v1/recoveries/{recovery_id}/verify
GET /api/v1/recovery
GET /api/v1/recovery-workspace
POST /api/v1/recovery-workspace/ai-review
POST /api/v1/recovery-workspace/record-outcome
GET /api/v1/recovery/lifecycle/accounts/{account_id}
POST /api/v1/recovery/lifecycle/accounts/{account_id}/allocations
POST /api/v1/recovery/lifecycle/accounts/{account_id}/responsibility
POST /api/v1/recovery/lifecycle/accounts/{account_id}/synchronize
POST /api/v1/recovery/lifecycle/accounts/{account_id}/transitions
GET /api/v1/recovery/lifecycle/billing-readiness
POST /api/v1/recovery/lifecycle/claims/{claim_id}
GET /api/v1/recovery/lifecycle/forecast
GET /api/v1/recovery/lifecycle/portfolio
PATCH /api/v1/recovery/{recovery_id}/status
GET /api/v1/submission-connectors
GET /api/v1/submissions
GET /api/v1/submissions/{submission_id}
POST /api/v1/submissions/{submission_id}/cancel
POST /api/v1/submissions/{submission_id}/refresh
POST /api/v1/tasks
GET /api/v1/tasks/claims/{claim_id}/timeline
GET /api/v1/tasks/manager
GET /api/v1/tasks/notifications
POST /api/v1/tasks/notifications/{notification_id}/read
GET /api/v1/tasks/performance
GET /api/v1/tasks/queue
POST /api/v1/tasks/sla-sweep
PUT /api/v1/tasks/users/{user_id}/skills
POST /api/v1/tasks/{task_id}/assign
POST /api/v1/tasks/{task_id}/transition
POST /api/v1/uploads/claims
GET /api/v1/users
POST /api/v1/users/accept-invite
POST /api/v1/users/invite
GET /api/v1/webhooks
POST /api/v1/webhooks
PATCH /api/v1/webhooks/{subscription_id}
DELETE /api/v1/webhooks/{subscription_id}
GET /api/v1/webhooks/{subscription_id}/deliveries
GET /api/v1/workflow-actions
GET /api/v1/workflow-definitions
POST /api/v1/workflow-definitions
GET /api/v1/workflow-definitions/{workflow_id}
PATCH /api/v1/workflow-definitions/{workflow_id}
POST /api/v1/workflow-definitions/{workflow_id}/execute
POST /api/v1/workflow-definitions/{workflow_id}/steps
PATCH /api/v1/workflow-definitions/{workflow_id}/steps/{step_id}
DELETE /api/v1/workflow-definitions/{workflow_id}/steps/{step_id}
GET /api/v1/workflow-executions/dashboard
GET /api/v1/workflow-executions/{execution_id}
POST /api/v1/workflow-executions/{execution_id}/approve
GET /api/v1/workflow-history
GET /api/v1/workflows
POST /api/v1/workflows
POST /api/v1/workflows/escalate-sweep
GET /api/v1/workflows/overdue
GET /api/v1/workflows/queue
GET /api/v1/workflows/queue/summary
GET /api/v1/workflows/{claim_id}
POST /api/v1/workflows/{claim_id}/transition
PUT /api/v1/workflows/{workflow_id}
DELETE /api/v1/workflows/{workflow_id}
POST /api/v1/workflows/{workflow_id}/disable
POST /api/v1/workflows/{workflow_id}/enable
GET /health
```

## Batch One Proposed Operations

Proposed operations are not registered contracts and are intentionally excluded from
the canonical manifest until implementation, permissions, tests, and documentation
pass.

| State | Proposed operation | Owner | Acceptance requirement |
|---|---|---|---|
| Under review | Normalize `/api/v1/claims/` to `/api/v1/claims` | Claims | Backward-compatible redirect/alias plan and client regression evidence. |
| Proposed | A document collection/search operation | Documents | Confirm whether claim-scoped listing already satisfies the workflow before adding a global tenant collection. |

## Unregistered Operations

The following paths appeared in earlier API inventories but are not exposed by the
current FastAPI application. They are intentionally excluded from the canonical
manifest until their owning modules implement and test the HTTP contract. Do not treat
these paths as callable APIs.

| Owner | Unregistered operations |
|---|---|
| Integrations | `GET /api/v1/integrations/{integration_id}/mappings`; `GET /api/v1/integrations/{integration_id}/runs`; `GET /api/v1/integrations/{integration_id}/runs/{run_id}/errors`; `POST /api/v1/integrations/{integration_id}/mappings`; `POST /api/v1/integrations/{integration_id}/mappings/preview`; `POST /api/v1/integrations/{integration_id}/runs/{run_id}/retry` |
| Payers | `GET /api/v1/payers/{payer_id}/claims/{claim_id}/validation`; `GET /api/v1/payers/{payer_id}/contracts`; `GET /api/v1/payers/{payer_id}/intelligence`; `GET /api/v1/payers/{payer_id}/profile`; `GET /api/v1/payers/{payer_id}/rules`; `POST /api/v1/payers/{payer_id}/contracts`; `POST /api/v1/payers/{payer_id}/profile`; `POST /api/v1/payers/{payer_id}/rules` |
| Payments | `GET /api/v1/payments/records/{payment_id}/candidates` |
| Recoveries | `GET /api/v1/recoveries/{recovery_id}/attributions`; `POST /api/v1/recoveries/interventions`; `POST /api/v1/recoveries/{recovery_id}/dispute`; `POST /api/v1/recoveries/{recovery_id}/resolve` |

## Compatibility Notes

- `PATCH /api/v1/appeals/{appeal_id}` persists reviewer-edited `appeal_text` and an
  optional section map only while the appeal is `draft` or `review`. Each successful
  edit creates a prior-version snapshot and audit record; approved or later appeals
  return HTTP 409 and remain immutable.
- `POST /api/v1/appeals/{appeal_id}/submit` records a submission completed outside
  Atlas and requires a non-empty payer confirmation or tracking reference. It does
  not transmit the appeal.
- `POST /api/v1/appeals/{appeal_id}/submissions` performs configured connector-backed
  electronic delivery and fails when the payer has no explicit route. Mock or sandbox
  transport is never selected implicitly. Human approval and explicit submission
  remain separate on both paths.
- `/api/v1/workflows` and `/api/v1/workflow-definitions` expose the documented
  trigger-versus-definition compatibility surfaces. Do not add a third workflow API.
- `/api/v1/payments` and `/api/v1/payments/records` are existing recovery and canonical
  evidence views. Extend the registered Payments owner; do not create claim-payment
  endpoints that bypass reconciliation.
- `GET /api/v1/payments/claims/{claim_id}/tracking` is a tenant-scoped claim read model
  over appeal, submission, matched payment, verified recovery, and invoice evidence.
  AI estimates and unverified recovery records never complete financial stages.
- `POST /api/v1/recovery-workspace/record-outcome` is a retained compatibility route
  that returns HTTP 410. Payment ingestion/reconciliation and recovery verification
  are the only supported paths for recording payment-backed financial outcomes.
- `/api/v1/dashboard` and `/api/v1/dashboard/summary` are distinct registered reads,
  not exact method/path duplicates.

## Verification

`apps/api/tests/test_architecture_contracts.py` compares this manifest with the
generated OpenAPI operation set and rejects duplicate method/path pairs. Focused API
tests remain required for behavior, authentication, RBAC, validation, tenant isolation,
audit, and error mapping.