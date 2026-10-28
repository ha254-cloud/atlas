# ADR 0002: Human Approval Before Appeal Submission

- Status: Accepted
- Date: 2026-08-01
- Owners: Product, Security, Revenue Cycle Operations

## Context

Atlas can analyze claims and generate appeal drafts with AI. Sending an appeal creates an external representation to a payer and can carry financial, contractual, privacy, and clinical consequences. Configurable workflows increase the risk that a tenant administrator could unintentionally turn draft generation into automatic submission.

## Decision

Appeal generation and appeal submission are separate capabilities. Workflow definitions may generate a draft and may pause at a human approval step. They may not submit an appeal, invoke a submission endpoint, or publish an event that represents submission.

Submission remains an explicit authenticated user action protected by submission-specific authorization, connector validation, and audit logging. Approval of a workflow execution does not itself submit an appeal.

The workflow action registry contains no submission action. Definition validation rejects unsupported actions and event publication that implies automatic submission.

## Consequences

- Revenue-cycle staff retain final control over every payer-facing appeal.
- Workflow automation can prepare and route work but cannot complete the external submission boundary.
- Adding automatic submission later requires a superseding ADR, product and security approval, segregation-of-duties design, connector controls, and complete audit evidence.
- Tenant-authored configurations that request automatic submission fail closed.
