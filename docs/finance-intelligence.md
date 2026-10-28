# Finance Intelligence

Finance Intelligence is the executive projection layer for Atlas Kenya v1.0. It
does not replace the hospital HIS or create a second financial ledger. It reads
tenant-scoped claims, canonical payments, attributed recoveries, recovery cases,
payers, and denials.

## API

All routes require authentication, the `analytics` entitlement, and
`view_analytics` permission.

- `GET /api/v1/finance/overview`
- `GET /api/v1/finance/executive`
- `GET /api/v1/finance/payers`
- `GET /api/v1/finance/denial-leakage`
- `GET /api/v1/finance/forecast?days=30`

Every query derives `organization_id` from authenticated context. No route accepts
tenant identity from request data.

## Metric Definitions

- Potential revenue: sum of claim billed amounts.
- Collected revenue: sum of cumulative claim paid amounts.
- Today's collections: positive canonical paid or partial payments dated today.
- Outstanding claims: non-negative billed minus paid balance per claim.
- Recoverable revenue: open recovery-case estimates, capped at each claim's
  outstanding balance.
- Atlas-attributed recoveries: canonical recovery records linked to payments.
- Unclassified leakage: outstanding balance not currently represented by an open
  recovery estimate. It is not automatically classified as permanently lost.
- Collection rate: collected revenue divided by potential revenue.
- Denial rate: denied claim count divided by claim count.
- Average payment days: payment date minus claim service date for matched positive
  payments.

The hospital revenue health score is version 1 of a transparent composite: 50%
collection rate, 25% inverse denial rate, and 25% payment timeliness, where 60 days
scores zero for timeliness. This is an operational indicator, not an accounting or
clinical quality measure.

The cash forecast is the sum of open recovery estimates multiplied by their
recorded recovery scores. It is explicitly probability-weighted and does not claim
that a payer will settle within the selected horizon.

## Currency and Reconciliation

Claim balances currently inherit the organization's configured ISO currency.
Executive and payer payment metrics include only canonical payments in that
currency. Reconciliation reports every observed payment currency so mixed-currency
records remain visible and are never silently aggregated.

## Work Queue

`GET /api/v1/workflows/queue` returns assigned work for staff and organization-wide
work for owners, administrators, and managers. Items include recovery probability,
priority, amount, due date, and overdue state. Managers can read aggregate counts at
`GET /api/v1/workflows/queue/summary`.

Automatic assignment policy is not implemented. The configurable workflow engine
can execute explicit assignment steps, but Atlas does not yet choose an assignee
without an approved tenant policy.

## Known Gaps

Department and clinician scorecards are intentionally unavailable because claims
do not yet reference governed tenant-owned department and clinician records. Atlas
does not infer those dimensions from free text. Branch/department/provider models,
claim currency snapshots, payment allocation/reversal ledgers, forecast calibration,
and production reconciliation controls remain release-plan work.
