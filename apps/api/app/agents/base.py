"""
BaseAgent — every specialist agent implements this same tiny interface,
so the orchestrator can run any of them (present or future) identically:
`await agent.run(context)` always returns an AgentResult.

Agents receive a single, already-populated ClaimContext (see
app.agents.context) instead of fetching their own data — this keeps them
simple, side-effect-free where possible, and easy to test in isolation.
"""

from abc import ABC, abstractmethod

from app.agents.models import AgentResult


class BaseAgent(ABC):
    # Unique task/agent identifier. Doubles as the AICallLog `task` name
    # for agents that make real AI Gateway calls, and as the AgentRegistry
    # lookup key.
    name: str = "base"

    def __init__(self, db=None, organization_id: int | None = None, ai_engine=None):
        # Every agent accepts the same constructor shape (even ones that
        # don't need `db`/`organization_id`/`ai_engine`) so the Orchestrator
        # and AgentRegistry can instantiate any of them uniformly.
        self.db = db
        self.organization_id = organization_id
        self.ai_engine = ai_engine

    @abstractmethod
    async def run(self, context) -> AgentResult:
        """Perform this agent's one job against `context` (a ClaimContext)
        and return a structured AgentResult. Must never raise — real
        failures should be caught and returned as a `status="failed"`
        AgentResult with a safe fallback `output`, so one agent failing
        doesn't take down the whole orchestration run."""
        raise NotImplementedError
