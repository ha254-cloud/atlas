"""
Data shapes shared across the multi-agent layer.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentResult:
    """The uniform return type of every agent's `run()`."""

    agent: str
    output: dict[str, Any]
    duration_ms: int
    status: str = "succeeded"  # "succeeded" | "failed" | "skipped"
    error: str | None = None
