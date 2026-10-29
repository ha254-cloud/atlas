# ADR 0004: Revenue Recovery Partner Operating Model

- Status: Accepted
- Date: 2026-08-01
- Owners: Product, finance, revenue operations, and architecture
- Review date: Before signing the first design-partner commercial agreement
- Related milestone: M1

## Context

Atlas is evolving from software used by a hospital team into a technology-enabled
Revenue Recovery Partner. It can prevent avoidable denials, operate recovery work,
reconcile resulting payments, and explain revenue leakage. A partner model creates
stronger alignment but also creates a financial-control obligation: Atlas must prove
which cash was recovered, why it is attributable, how fees were calculated, and how
reversals or disputes are corrected.

A payer approval, remittance advice, HIS posting, and bank settlement are different
facts. A payment received after an Atlas appeal is not automatically caused by Atlas.
Prevention is valuable but counterfactual: an avoided denial cannot normally be
proven claim by claim. Charging a success fee without these distinctions would create
unreliable hospital invoices and undermine trust.

## Decision

### Commercial Model

Atlas uses a hybrid commercial model with independently contracted components:

1. **Onboarding and data-readiness fee** for workflow discovery, file mapping,
   configuration, training, and controlled go-live.
2. **Platform and managed-service retainer** for the Prevention and Intelligence
   Engines, workflow operations, reporting, and agreed service levels.
3. **Recovery success fee** only on contract-eligible, attributable, net settled
   cash from post-denial or underpayment interventions.

Prevention value is reported as revenue protected, risk removed, clean-claim rate,
and payment acceleration. It is not invoiced as recovered cash. A future shared-savings
arrangement requires an agreed historical baseline, comparable cohorts, exclusions,
minimum sample size, and a signed measurement schedule.

Fee percentage, tiers, caps, exclusions, VAT treatment, currency, payment terms,
dispute period, and evidence standard are versioned contract configuration. Example
percentages are not product defaults. Kenyan tax treatment requires finance/legal
approval before production invoicing.

### End-To-End Operating Flow

1. **Onboard and baseline**: configure organization, branches, departments, users,
   role templates, payers, channels, fee agreement, recovery eligibility, historical
   performance baseline, and approved import/export profiles.
2. **Ingest**: accept CSV first, then Excel, SFTP, or API. Preserve source file,
   source row, branch, payer, amount, currency, identifiers, and import version.
   Invalid rows enter remediation; retries are idempotent.
3. **Prevent**: validate eligibility, authorization, coding, tariffs, duplicate risk,
   and required evidence using versioned Kenya/payer/organization rules. Produce a
   risk assessment and explainable corrections. A human corrects the source claim;
   Atlas records the correction and outcome but does not invent payer policy.
4. **Observe submission/outcome**: record the hospital's original claim submission
   reference and channel where available. Ingest acknowledgements, denials,
   underpayments, and requests for information from files, email, portals, or APIs.
5. **Open recovery case**: prioritize by recoverable KES, probability, age, evidence,
   and contractual eligibility. Record the denial reason and assign an owner and SLA.
6. **Prepare intervention**: collect documents, generate an evidence-grounded appeal
   or correction, and record every Atlas and hospital action in an intervention ledger.
7. **Human review**: an authorized hospital user reviews the letter, evidence,
   recipient, and requested amount. Editing and approval are audited. Approval never
   submits automatically.
8. **Submit and follow up**: use the payer's verified portal, email, file, API, or
   manual procedure. Store external references, delivery evidence, status history,
   conversation thread, follow-up schedule, and failures.
9. **Detect payment evidence**: ingest payer advice, payment reports, HIS postings,
   APIs, and bank statements. OCR or AI may extract candidate facts but cannot confirm
   a financial match without deterministic evidence or human approval.
10. **Match and reconcile**: exact references are preferred. Deterministic composite
    matching may use payer, member/claim reference, amount, currency, and date window.
    Fuzzy matches are suggestions. Support one bulk settlement across many claims,
    multiple partial settlements for one claim, deductions, withholding, and reversals.
11. **Attribute**: calculate contract-eligible recovery only after an eligible Atlas
    intervention predates the recovery outcome and exclusions are applied. Preserve
    the calculation inputs and contract version in an immutable attribution version.
12. **Verify and dispute**: hospital finance verifies the match and attribution.
    A configured dispute window follows. Disputed items are excluded from invoices;
    resolved changes append a new version rather than overwriting financial history.
    If an undisputed item was already invoiced and is then disputed within the
    configured window, a resolution that reduces eligibility issues an immutable
    credit note in the same transaction.
13. **Invoice**: group undisputed, verified attribution versions by organization,
    legal entity, currency, tax treatment, and billing period. Each line shows claim,
    payer, settled amount, eligible amount, intervention, fee rule, fee, and evidence.
14. **Settle Atlas invoice**: record sending, receipt, hospital payment, credits, and
    aging separately from hospital recovery accounting.
15. **Learn and report**: update prevention, recovery, payer, branch, department, and
    analyst metrics from governed events. Never train on disputed or unverified labels.

### Three Engines

The engines are product capabilities over shared records, not duplicate databases:

- **Prevention Engine**: pre-submission validation, denial prediction, missing-evidence
  detection, correction workflow, and revenue-protected measurement.
- **Recovery Engine**: denial/underpayment intake, prioritization, evidence, appeal,
  human approval, payer communication, follow-up, payment reconciliation, attribution,
  dispute, and invoicing.
- **Intelligence Engine**: payer payment time, aging, denial cost, branch/department
  leakage, documentation patterns, recoverability, cash forecast, intervention
  effectiveness, analyst workload, and executive opportunities.

All three use the same claim, payer, document, event, payment, and organization
identity. An engine does not own a second claim or payment record.

### Payment Evidence States

Atlas distinguishes:

- `advised`: payer communication states an amount is approved or scheduled;
- `posted`: the hospital HIS or payer ledger allocates an amount to a claim;
- `cash_confirmed`: bank or finance-controlled evidence confirms settlement;
- `reversed`: all or part of previously recognized settlement was reversed;
- `unmatched`: evidence exists but allocation is unresolved.

Dashboards may show advised and posted amounts separately. `recovered cash` and
success-fee invoices use the contract's evidence standard, which defaults to
`cash_confirmed` for the partner model.

### Attribution Rules

A success-fee attribution is eligible only when all required conditions hold:

1. The organization, branch, claim, payer, amount, and currency are known.
2. The claim was enrolled in the contracted recovery scope before the cutoff.
3. An eligible intervention is recorded before the payer outcome or settlement.
4. The payment allocation is confirmed and is not already attributed elsewhere.
5. Pre-Atlas payments, routine undisputed payments, patient payments, capitation,
   unrelated settlements, and contract exclusions are removed.
6. The eligible amount is net of reversals, refunds, non-contractual adjustments,
   and previously recognized amounts.
7. The fee schedule effective for the intervention/payment is snapshotted.
8. Hospital verification and the dispute policy are satisfied before invoicing.

Temporal sequence is necessary but not sufficient evidence of causation. A configurable
policy determines which intervention types qualify, such as corrected resubmission,
appeal, missing-document response, underpayment challenge, or documented follow-up.

### Financial Formula

For one attribution version:

```text
eligible_net_recovery
  = confirmed_allocated_cash
  - pre_atlas_or_excluded_amount
  - reversals_and_refunds
  - previously_attributed_amount

success_fee
  = eligible_net_recovery * contracted_fee_rate
```

VAT or other tax is applied to the Atlas fee according to the approved tax profile,
not to the hospital's recovered principal. Decimal arithmetic and explicit rounding
rules apply. Different currencies are never combined on one invoice without a
governed conversion and accounting policy.

## Required Domain Changes

The current implementation is a functional orchestration proof, not yet a sufficient
partner-billing ledger. Before production success-fee billing it requires:

- recovery engagement/contract scope and baseline versions;
- append-only intervention and attribution versions;
- payment evidence and many-to-many payment allocation records;
- explicit matching confidence, method, reviewer, and source provenance;
- partial payment, bulk settlement, reversal, refund, and adjustment lifecycles;
- recovery verification, dispute, resolution, and invoice-credit workflows;
- immutable invoice snapshots and credit notes rather than destructive regeneration;
- end-to-end actor, reason, before/after, organization, branch, and correlation IDs.

The existing rule that any matched `paid` or `partial` payment creates a recovery must
not be used as the production success-fee eligibility rule. Existing one-payment /
one-recovery and one-recovery-per-submission constraints must be replaced by allocation
and attribution ledgers without losing historical records.

## Alternatives Considered

- **Pure SaaS subscription**: simpler, but under-aligns pricing with recovery outcomes
  and understates the operational partnership. Retained as one component.
- **Pure success fee on all detected payments**: rejected because prevention is
  counterfactual and payment timing alone does not prove Atlas contribution.
- **Success fee on payer approvals**: rejected because approved amounts may never
  settle or may later be reversed.
- **Atlas-controlled hospital bank account**: rejected for v1 due to custody,
  licensing, reconciliation, fraud, and operational risk. Hospitals retain custody.
- **AI-confirmed payment matching**: rejected. AI may suggest; deterministic rules or
  authorized human confirmation establish financial state.

## Consequences

- Atlas can sell measurable outcomes while keeping hospital invoices defensible.
- Prevention and intelligence can launch before counterfactual shared-savings models.
- Payment reconciliation and attribution become financial subledgers requiring the
  same rigor as invoicing, not dashboard calculations.
- Managed-service operations require named queues, SLAs, quality review, segregation
  of duties, support hours, and capacity planning in addition to software uptime.
- Hospital finance retains final verification; Atlas cannot silently mark its own fee
  as earned.

## Validation

- Reconcile imported claim and payment totals to hospital finance control totals.
- Replay exact, partial, bulk, overpayment, deduction, refund, and reversal fixtures.
- Prove that advised/posted amounts do not enter cash-confirmed fee invoices.
- Prove that payments without prior eligible interventions produce zero success fee.
- Prove attribution and invoices are idempotent and cross-tenant/cross-branch safe.
- Recalculate every invoice line independently from immutable evidence and contract
  snapshots and obtain the same amount and rounding result.
- Exercise dispute, resolution, reversal after invoice, credit note, and audit export.
- Compare Prevention Engine predictions against held-out outcomes and report calibration,
  false positives, and prevented-value methodology separately from recovered cash.

## Intentional Debt

- **Risk:** Current recovery creation equates a matched positive payment with recovery.
  **Mitigation:** retain mandatory human verification and prohibit production
  contingency invoicing until the attribution ledger is implemented. **Owner:**
  revenue engineering and finance. **Removal condition:** partner-billing validation
  above passes. **Target:** M1 design-partner commercial go-live.
- **Risk:** Payment advice, bank statement, and email/PDF ingestion are not complete.
  **Mitigation:** pilot with finance-controlled payment exports and manual evidence
  review. **Owner:** integrations and revenue operations. **Removal condition:** one
  production-like reconciliation cycle passes. **Target:** M1.
