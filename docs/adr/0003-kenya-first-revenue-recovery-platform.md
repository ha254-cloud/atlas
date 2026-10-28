# ADR 0003: Kenya-First Revenue Recovery Platform

- Status: Accepted
- Date: 2026-08-01
- Owners: Product, architecture, and revenue operations
- Review date: After the first Kenyan design-partner workflow study
- Related milestone: M1

## Context

Kenyan hospitals already operate hospital information, billing, and clinical
systems. Their revenue teams work across payer portals, email, CSV and Excel
files, supporting documents, and manual follow-up. Atlas creates value by
recovering revenue and explaining where revenue is being lost, not by replacing
those systems or reproducing a US clearinghouse workflow.

The payer landscape includes SHA, private medical insurers, employer schemes,
NGOs, and county governments. Multi-branch hospital groups need consolidated
governance with branch-level operations and reporting. Payer rules, terminology,
documents, and submission channels vary and must be learned from authoritative
sources and design partners rather than inferred.

## Decision

1. Atlas is an **AI Revenue Recovery and Payer Intelligence Platform**. Hospital
   systems remain the source of clinical and billing records. CSV is the first
   onboarding contract; Excel, SFTP, email, portal, and verified APIs extend it.
2. `Payer` is the common domain concept for SHA, insurers, employer schemes,
   NGOs, and government programs. Tenant payer records remain the routing
   authority for submission, status, reconciliation, rules, and reporting.
3. SHA remains a payer in the shared core. A future `app.sha` package may own
   verified SHA-specific eligibility, verification, claim, and reconciliation
   policies, but it must extend shared payer contracts and must not duplicate
   claims, payments, documents, or tenant ownership. It is created only after
   workflow discovery demonstrates distinct behavior.
4. `Organization` remains the tenant security boundary. The operating hierarchy
   is Organization -> Branch -> Department. Branches are directly tenant-owned;
   departments are scoped through a branch. Claims carry organization and branch
   context and may carry a department when the source supports it. Database
   constraints and repositories must reject a branch from a different organization.
5. Users may serve more than one branch. Branch access uses a tenant-scoped
   membership table with role/permission assignments, not a list stored on the
   user. Claims Officer, Revenue Officer, Finance Manager, Medical Records Officer,
   Branch Manager, Hospital Administrator, and CEO are configurable hospital role
   templates over stable permissions; authorization does not depend on display
   titles. Organization-level roles may see approved rollups; branch roles see only
   assigned branches. Atlas Support is a separately governed platform identity,
   never an ordinary hospital role.
6. Every persisted monetary fact stores an ISO 4217 currency with its amount.
   New Kenyan records default to `KES` through country/tenant configuration, but
   ingestion snapshots the currency on the claim or transaction. Reports do not
   sum different currencies without an explicit, dated exchange-rate policy.
7. Denial knowledge is layered and versioned: global taxonomy -> country pack ->
   payer rule -> organization override. Hospitals can add local reasons without
   mutating shared reference data. Every rule records provenance, effective dates,
   approval state, and supersession history before it may ground AI output.
8. The Kenya Knowledge Pack is a versioned evidence product containing local
   terminology, denial mappings, document expectations, appeal structures, and
   verified payer rules. AI calls continue through `AIGateway`; prompts identify
   the pack and rule versions used and must not invent missing payer policy.
9. CSV and Excel are first-class import and export formats. File profiles map a
   hospital's columns into canonical data, retain source provenance, provide
   row-level validation, and make retries idempotent. Scheduled reports use the
   same authorized query and export services as interactive reports.
10. Email is a first-class payer workflow with outbound message, PDF and evidence
    attachments, delivery state, conversation threading, and immutable audit.
    Inbound replies require authenticated mailbox integration, malware scanning,
    tenant matching, and human review before changing financial or claim state.
11. Claim documents are evidence records. Storage, access, retention, malware
    scanning, extraction provenance, and redaction must be complete before AI may
    rely on extracted text in an appeal. Human approval remains mandatory.
12. Mobile approval is a responsive, authenticated web workflow. Email, SMS, or
    WhatsApp may notify and deep-link to Atlas, but protected claim data and the
    approval act remain inside Atlas. Approval never causes automatic submission.
13. Offline-friendly means durable server queues, idempotent retries, resumable
    uploads, and a PWA outbox for explicitly supported actions. Sensitive claim
    data is not cached on a device by default. Offline financial mutations and
    approvals are out of scope until conflict and device-security controls exist.
14. Day-one intelligence prioritizes outstanding claims by payer, 30/60/90 aging,
    denial cost, collections, balances, payer payment time, recovery rate, and
    analyst productivity. Department and clinician documentation signals are shown
    only when source attribution and sample size support them and must be framed as
    process-improvement evidence, not unsupported individual blame. Advanced revenue
    recovery intelligence must show its cohort, date range, currency, data freshness,
    and evidence behind estimates.
15. Country modules configure terminology, packs, templates, defaults, and
    supported channels. Core claims, payer, payment, document, workflow, audit,
    and tenancy contracts remain country-neutral so Uganda, Tanzania, and Rwanda
    can be added without copying the platform.

## Pilot Sequence

1. Observe and document one design partner's HIS export, denial, document,
   approval, email/portal, payment-report, and month-end reporting workflows.
2. Add branch/department ownership and claim currency with migration, audit,
   permissions, import mapping, and cross-tenant/cross-branch tests.
3. Deliver reusable CSV/Excel import profiles, row-level remediation, and exports.
4. Deliver configurable denial reasons and a reviewed Kenya Knowledge Pack v1.
5. Complete claim evidence handling and an audited outbound email appeal workflow.
6. Reconcile payer CSV/Excel/portal reports into canonical payments and recoveries.
7. Deliver branch-aware operational reports and evidence-backed executive revenue
   recovery intelligence.
8. Certify one real payer workflow only after protocol access and operational
   ownership are confirmed; build an SHA extension only if discovery supports it.

## Explicit Non-Goals For V1

- Replacing a hospital HIS, billing, clinical, or accounting system.
- Assuming US X12/CARC/clearinghouse behavior is valid in Kenya.
- Claiming live SHA or private-payer connectivity before certification.
- Native mobile applications, unattended appeal submission, or approval through
  email or WhatsApp.
- Cross-currency financial aggregation without a governed conversion policy.
- Full offline replication of protected health or financial data.

## Consequences

- Existing generic payer, claim, payment, document, and workflow modules remain
  the shared core; Kenya-specific behavior enters through typed, versioned policy.
- Branch filtering becomes an authorization concern, not merely a report filter.
- Current organization currency defaults, global denial codes, generic roles,
  document handling, and retry queues are foundations rather than completion of
  the requirements above.
- Feature readiness requires evidence from real hospital operating workflows and
  must distinguish configured manual handling from automated integration.

## Validation

- Design-partner acceptance tests use representative, de-identified HIS and payer
  files and compare Atlas totals with finance-controlled source totals.
- Cross-organization and cross-branch tests cover API, tasks, exports, documents,
  dashboards, AI context, audit, and cache keys.
- Import/export round trips preserve identifiers, amounts, currencies, and source
  provenance; retries do not duplicate claims or payments.
- Report fixtures verify aging boundaries, payer payment time, recovery rates,
  productivity attribution, and same-currency totals.
- AI evaluations cite the exact knowledge-pack and payer-rule versions used and
  penalize unsupported policy claims.
- Email tests cover recipient allowlists, attachments, delivery failure, threading,
  audit, malware rejection, and human review of inbound state changes.
