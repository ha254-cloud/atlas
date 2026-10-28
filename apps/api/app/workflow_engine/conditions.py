"""
Safe condition/expression evaluation for WORKFLOW-step CONDITION branches
(e.g. "claim.billed_amount > 5000 AND risk.recovery_probability_pct > 80").

Organizations author these expressions themselves, so this deliberately
does NOT use Python's eval()/exec() (or anything that walks arbitrary
object attributes) — that would let an org admin's stored expression run
arbitrary code inside the API process, an OWASP-relevant injection risk.
Instead this is a small hand-rolled evaluator that only ever does dict-key
lookups against a plain, already-serialized context and a fixed set of
comparison operators.

Supported grammar (v1, deliberately simple):
    <dotted.path> <op> <value>  [ AND <dotted.path> <op> <value> ... ]
    [ OR <dotted.path> <op> <value> [ AND ... ] ... ]

- OR has the lowest precedence, AND binds tighter than OR (both keywords
  are case-insensitive).
- No parentheses / nested grouping in v1 — write conditions as a flat
  OR-of-ANDs, which covers everything the Sprint 5 spec's examples need.
- <value> may be a number, true/false, null, a quoted string, or a bare
  word (treated as a string).
- <dotted.path> is resolved by walking dict keys in the execution context
  (e.g. "risk" -> "recovery_probability_pct") — never attribute access,
  so it can never reach outside the plain data the engine put there.
"""

import re
from typing import Any

_ATOM_RE = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*(>=|<=|==|!=|>|<)\s*(.+?)\s*$")
_OR_SPLIT_RE = re.compile(r"\s+OR\s+", re.IGNORECASE)
_AND_SPLIT_RE = re.compile(r"\s+AND\s+", re.IGNORECASE)


class ConditionError(ValueError):
    """Raised when a CONDITION step's expression is malformed."""


def evaluate_condition(expression: str, context: dict) -> bool:
    if not expression or not expression.strip():
        raise ConditionError("Condition expression is empty.")

    or_groups = _OR_SPLIT_RE.split(expression)
    return any(
        all(_evaluate_atom(atom, context) for atom in _AND_SPLIT_RE.split(group))
        for group in or_groups
    )


def _evaluate_atom(atom: str, context: dict) -> bool:
    match = _ATOM_RE.match(atom)
    if not match:
        raise ConditionError(f"Unrecognized condition clause: {atom!r}")
    path, op, raw_value = match.groups()
    actual = _resolve_path(path, context)
    expected = _parse_value(raw_value)
    return _compare(actual, op, expected)


def _resolve_path(path: str, context: dict) -> Any:
    value: Any = context
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in ("null", "none"):
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if actual is None:
        if op == "==":
            return expected is None
        if op == "!=":
            return expected is not None
        return False
    try:
        if op == ">":
            return actual > expected
        if op == "<":
            return actual < expected
        if op == ">=":
            return actual >= expected
        if op == "<=":
            return actual <= expected
        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
    except TypeError:
        return False
    return False
