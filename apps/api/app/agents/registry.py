"""
AgentRegistry — avoids hardcoding the roster of agents into the
orchestrator. Adding a new agent (Fraud Detection, Contract Validation,
Payment Integrity, ...) means registering it here, not editing
orchestrator.py.

Stores agent *classes* (not instances) because several agents need
request-scoped dependencies (a db session, organization_id) that only
exist once a specific claim/org is being analyzed — the orchestrator
instantiates each one uniformly via `registry.get(name)(db, organization_id)`.
"""

from app.agents.base import BaseAgent


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, type[BaseAgent]] = {}

    def register(self, agent_cls: type[BaseAgent]) -> None:
        self._agents[agent_cls.name] = agent_cls

    def get(self, name: str) -> type[BaseAgent]:
        cls = self._agents.get(name)
        if cls is None:
            raise KeyError(f"Unknown agent: '{name}'")
        return cls

    def list_names(self) -> list[str]:
        return list(self._agents.keys())


# Module-level singleton — imported everywhere.
registry = AgentRegistry()


def _register_defaults() -> None:
    from app.agents.appeal.agent import AppealAgent
    from app.agents.coding.agent import CodingAgent
    from app.agents.compliance.agent import ComplianceAgent
    from app.agents.documentation.agent import DocumentationAgent
    from app.agents.recovery.agent import RecoveryAgent
    from app.agents.risk.agent import RiskAgent

    for agent_cls in (
        CodingAgent,
        DocumentationAgent,
        ComplianceAgent,
        RiskAgent,
        RecoveryAgent,
        AppealAgent,
    ):
        registry.register(agent_cls)


_register_defaults()
