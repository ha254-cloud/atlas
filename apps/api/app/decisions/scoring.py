"""
Decision Engine (Sprint 6) — computes a 0-100 Decision Score and an
economically rational recommended_action for a single claim, combining:

    recovery probability     30%
    claim amount              25%
    filing deadline urgency  20%
    AI confidence              10%
    payer responsiveness      10%
    analyst effort               5%

This is deliberately NOT another AI/LLM call — every input is either
already computed by an earlier engine (ClaimAnalyzer/RiskAgent/
RecoveryAgent from Sprint 4, via app.decisions.service.DecisionService)
or is real historical/persisted data (PayerStatistics). The Decision
Engine's only job is to weigh those signals into one auditable number
plus a plain-English "why" — see DecisionEngine.evaluate().

Weights/thresholds are fixed module constants for now, not a database
row. A future "configurable weights per organization" feature (explicitly
named in the product spec as a later step) could read overrides from a
new settings table and pass them into DecisionEngine(weights=...) without
touching any of the scoring math below — flagged here rather than built,
since no config surface for it was requested this round.
"""

from dataclasses import dataclass, field
from decimal import Decimal

WEIGHTS = {
    "recovery_probability": 0.30,
    "claim_amount": 0.25,
    "filing_urgency": 0.20,
    "ai_confidence": 0.10,
    "payer_responsiveness": 0.10,
    "analyst_effort": 0.05,
}

# Balance above which the claim-amount component maxes out at 100 — matches
# the RecoveryEngine's own $5,000 "critical" threshold elsewhere in this
# codebase (app.recovery.engine.RecoveryEngine._determine_priority), not an
# arbitrary new number.
CLAIM_AMOUNT_CAP = Decimal("5000")

# Rough analyst hourly-equivalent cost used to translate a qualitative
# effort level into a dollar figure for the ROI calculation. Approximate
# by design — always surfaced in the reasoning trail, never presented as
# precise accounting.
EFFORT_COST_USD = {"low": 50.0, "medium": 150.0, "high": 400.0}
EFFORT_SCORE = {"low": 100.0, "medium": 60.0, "high": 20.0}

# Decision-score floor for recommending "appeal" outright once none of the
# harder blockers (compliance, negative ROI, missing docs) apply.
APPEAL_SCORE_THRESHOLD = 40


@dataclass
class DecisionInput:
    balance: Decimal  # billed - paid
    recovery_probability_pct: float  # 0-100
    ai_confidence_pct: float  # 0-100
    analyst_effort: str  # low|medium|high
    days_until_deadline: int | None = None  # None = unknown/no active deadline
    payer_avg_payment_days: float | None = None  # None = no payer history yet
    documentation_gaps: list = field(default_factory=list)
    awaiting_authorization: bool = False
    compliance_blocking: bool = False


@dataclass
class DecisionOutput:
    decision_score: Decimal
    recommended_action: str
    potential_recovery: Decimal
    estimated_effort_cost: Decimal
    expected_roi: Decimal | None
    confidence: Decimal
    reasoning: list


class DecisionEngine:
    def evaluate(self, inputs: DecisionInput) -> DecisionOutput:
        reasoning: list[str] = []

        recovery_component = max(0.0, min(100.0, inputs.recovery_probability_pct))

        amount_component = float(min(inputs.balance, CLAIM_AMOUNT_CAP) / CLAIM_AMOUNT_CAP * 100)

        urgency_component, urgency_note = self._urgency_score(inputs.days_until_deadline)
        if urgency_note:
            reasoning.append(urgency_note)

        confidence_component = max(0.0, min(100.0, inputs.ai_confidence_pct))

        responsiveness_component, responsiveness_note = self._responsiveness_score(
            inputs.payer_avg_payment_days
        )
        if responsiveness_note:
            reasoning.append(responsiveness_note)

        effort_component = EFFORT_SCORE.get(inputs.analyst_effort, 60.0)

        decision_score = (
            recovery_component * WEIGHTS["recovery_probability"]
            + amount_component * WEIGHTS["claim_amount"]
            + urgency_component * WEIGHTS["filing_urgency"]
            + confidence_component * WEIGHTS["ai_confidence"]
            + responsiveness_component * WEIGHTS["payer_responsiveness"]
            + effort_component * WEIGHTS["analyst_effort"]
        )

        potential_recovery = (inputs.balance * Decimal(str(recovery_component / 100))).quantize(
            Decimal("0.01")
        )

        effort_cost = Decimal(str(EFFORT_COST_USD.get(inputs.analyst_effort, 150.0)))

        expected_roi = None
        if effort_cost > 0:
            expected_roi = (potential_recovery / effort_cost).quantize(Decimal("0.01"))

        action, action_reason = self._decide_action(
            inputs, potential_recovery, effort_cost, decision_score
        )
        reasoning.insert(0, action_reason)

        reasoning.append(f"Recovery probability {inputs.recovery_probability_pct:.0f}%")
        reasoning.append(f"Outstanding balance ${inputs.balance:,.2f}")
        if inputs.documentation_gaps:
            reasoning.append("Missing documentation: " + ", ".join(inputs.documentation_gaps))
        if expected_roi is not None:
            reasoning.append(
                f"Estimated ROI: {expected_roi:.1f}x "
                f"(recover ~${potential_recovery:,.2f} vs ~${effort_cost:,.0f} effort cost)"
            )

        return DecisionOutput(
            decision_score=Decimal(str(round(decision_score, 2))),
            recommended_action=action,
            potential_recovery=potential_recovery,
            estimated_effort_cost=effort_cost,
            expected_roi=expected_roi,
            confidence=Decimal(str(round(confidence_component, 2))),
            reasoning=reasoning,
        )

    def _urgency_score(self, days_until_deadline: int | None):
        if days_until_deadline is None:
            return 50.0, None
        if days_until_deadline <= 0:
            return 100.0, "Filing deadline has passed or is today"
        if days_until_deadline <= 7:
            return 95.0, f"Filing deadline in {days_until_deadline} days"
        if days_until_deadline <= 30:
            return 70.0, f"Filing deadline in {days_until_deadline} days"
        if days_until_deadline <= 90:
            return 40.0, None
        return 15.0, None

    def _responsiveness_score(self, avg_days: float | None):
        if avg_days is None:
            return 50.0, None
        if avg_days <= 15:
            return 90.0, f"Payer historically pays within {avg_days:.0f} days"
        if avg_days <= 30:
            return 70.0, f"Payer historically pays within {avg_days:.0f} days"
        if avg_days <= 60:
            return 45.0, None
        return 20.0, f"Payer historically slow to pay (~{avg_days:.0f} days)"

    def _decide_action(
        self, inputs: DecisionInput, potential_recovery, effort_cost, decision_score
    ):
        if inputs.awaiting_authorization:
            return (
                "await_authorization",
                "Prior authorization is pending — no further action until it resolves",
            )
        if inputs.compliance_blocking:
            return (
                "write_off",
                "Filing deadline has expired or authorization is missing — recovery is not viable",
            )
        if effort_cost > 0 and potential_recovery < effort_cost:
            return (
                "write_off",
                f"Expected recovery (${potential_recovery:,.2f}) is less than the estimated effort "
                f"cost (${effort_cost:,.2f}) — not economically worth pursuing",
            )
        if inputs.documentation_gaps:
            return (
                "upload_documentation",
                "Required documentation is missing before this claim can be appealed",
            )
        if decision_score >= APPEAL_SCORE_THRESHOLD:
            return "appeal", "Recovery probability and claim value justify pursuing an appeal"
        return "monitor", "Below the threshold to act now — keep monitoring for new information"
