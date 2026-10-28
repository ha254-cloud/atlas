"""
AgentOrchestrator — Atlas' "AI workforce" coordinator (Sprint 4).

Workflow:
    Load ClaimContext once
      -> run Coding, Documentation, Compliance, Risk agents IN PARALLEL
         (none of them depend on each other)
      -> run Recovery agent (needs Risk + Compliance's outputs, so it
         runs after phase 1 and reads them via context.agent_outputs)
      -> run Appeal agent, but ONLY if Recovery recommended "appeal" and
         Compliance found no blocking issue — not every claim should be
         appealed
      -> resolve conflicts explicitly (e.g. Risk says recoverable but
         Compliance says timely filing expired -> final decision says
         appeal is impossible, with a reason, instead of averaging)
      -> persist a full execution log + the merged analysis

The orchestrator doesn't make decisions itself — it coordinates
specialists and adjudicates disagreements between them.

Deliberately NOT the general, hospital-configurable "Workflow Engine"
(IF/THEN business rules editable per-org) described as the *next*
milestone — the phase ordering and conflict-resolution logic below are
still code. That generalization is future work.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.context import build_context
from app.agents.registry import registry
from app.ai.cost_tracking import ai_call_context
from app.models.agent_execution import AgentExecutionLog
from app.models.claim_analysis import AnalysisStatus, ClaimAnalysis

logger = logging.getLogger(__name__)

# These four don't depend on each other's output — run them concurrently.
PARALLEL_AGENTS = ("coding", "documentation", "compliance", "risk")


class AgentOrchestrator:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    async def run(self, claim_id: int) -> dict[str, Any]:
        import asyncio

        run_id = uuid.uuid4().hex
        context = build_context(self.db, self.organization_id, claim_id)

        with ai_call_context(organization_id=self.organization_id, claim_id=claim_id):
            phase1_agents = [
                registry.get(name)(self.db, self.organization_id) for name in PARALLEL_AGENTS
            ]
            phase1_results = await asyncio.gather(*(agent.run(context) for agent in phase1_agents))
            for result in phase1_results:
                context.agent_outputs[result.agent] = result.output
                self._log_execution(run_id, claim_id, result)

            recovery_agent = registry.get("recovery")(self.db, self.organization_id)
            recovery_result = await recovery_agent.run(context)
            context.agent_outputs["recovery"] = recovery_result.output
            self._log_execution(run_id, claim_id, recovery_result)

            appeal_output = None
            compliance_output = context.agent_outputs.get("compliance", {})
            if recovery_result.output.get(
                "recommended_action"
            ) == "appeal" and not compliance_output.get("blocking"):
                appeal_agent = registry.get("appeal")(self.db, self.organization_id)
                appeal_result = await appeal_agent.run(context)
                context.agent_outputs["appeal"] = appeal_result.output
                self._log_execution(run_id, claim_id, appeal_result)
                appeal_output = appeal_result.output
            else:
                self._log_skip(
                    run_id,
                    claim_id,
                    "appeal",
                    reason=(
                        "Recovery Agent did not recommend an appeal, or Compliance "
                        "Agent found a blocking issue."
                    ),
                )

        risk_output = context.agent_outputs.get("risk", {})
        conflicts = self._detect_conflicts(risk_output, compliance_output, recovery_result.output)

        final_decision = {
            "recommended_action": recovery_result.output.get("recommended_action"),
            "reason": recovery_result.output.get("reason"),
            "priority": risk_output.get("priority", "low"),
            "risk_score": risk_output.get("risk_score"),
            "recovery_probability_pct": risk_output.get("recovery_probability_pct"),
            "expected_recovery": recovery_result.output.get("estimated_recovery"),
            "estimated_effort": risk_output.get("estimated_effort"),
            "appeal_id": appeal_output.get("appeal_id") if appeal_output else None,
        }

        result = {
            "run_id": run_id,
            "claim_id": claim_id,
            "agent_outputs": context.agent_outputs,
            "conflicts": conflicts,
            "final_decision": final_decision,
        }

        self._persist_analysis(claim_id, result)
        return result

    def _detect_conflicts(self, risk: dict, compliance: dict, recovery: dict) -> list[dict]:
        """Surface disagreements explicitly rather than blending scores —
        e.g. the canonical example: Risk says recoverable, Compliance says
        timely filing expired."""
        conflicts = []
        if risk.get("recovery_probability_pct", 0) >= 70 and compliance.get("blocking"):
            conflicts.append(
                {
                    "agents": ["risk", "compliance"],
                    "description": (
                        f"Risk Agent found high recovery potential "
                        f"({risk.get('recovery_probability_pct')}%) but Compliance Agent "
                        f"found a blocking issue."
                    ),
                    "resolution": (
                        f"Recovery strategy overridden to '{recovery.get('recommended_action')}' — "
                        f"{recovery.get('reason')}"
                    ),
                }
            )
        return conflicts

    def _log_execution(self, run_id: str, claim_id: int, result) -> None:
        self._write_log(
            run_id, claim_id, result.agent, result.status, result.duration_ms, result.error
        )

    def _log_skip(self, run_id: str, claim_id: int, agent_name: str, reason: str) -> None:
        self._write_log(run_id, claim_id, agent_name, "skipped", 0, reason)

    def _write_log(self, run_id, claim_id, agent_name, status, duration_ms, error_message) -> None:
        # Best-effort, like AICallLog's log_ai_call — a logging failure
        # must never break the actual orchestration.
        try:
            self.db.add(
                AgentExecutionLog(
                    organization_id=self.organization_id,
                    claim_id=claim_id,
                    run_id=run_id,
                    agent_name=agent_name,
                    status=status,
                    duration_ms=duration_ms,
                    error_message=error_message,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to log agent execution for claim %s", claim_id)

    def _persist_analysis(self, claim_id: int, result: dict) -> None:
        try:
            analysis = (
                self.db.query(ClaimAnalysis)
                .filter(
                    ClaimAnalysis.claim_id == claim_id,
                    ClaimAnalysis.organization_id == self.organization_id,
                )
                .first()
            )
            if analysis is None:
                analysis = ClaimAnalysis(
                    organization_id=self.organization_id,
                    claim_id=claim_id,
                    analysis_status=AnalysisStatus.COMPLETED,
                )
                self.db.add(analysis)
            analysis.multi_agent_result = result
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to persist multi-agent result for claim %s", claim_id)
