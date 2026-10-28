"""
Atlas' Multi-Agent Intelligence layer (Sprint 4).

Instead of one monolithic LLM call per claim, specialist agents each
answer one narrow question (coding correctness, documentation
completeness, compliance risk, overall risk/priority, recovery
strategy, appeal drafting) and an orchestrator coordinates them,
resolves disagreements explicitly, and keeps an audit trail.

See app.agents.orchestrator.AgentOrchestrator for the entry point.
"""
