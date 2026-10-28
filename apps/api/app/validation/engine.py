"""
ValidationEngine — runs all pre-submission rules against a CanonicalClaim.

Used by ClaimProcessor before persistence:
  - Any "error" severity issue blocks the claim (raises ClaimValidationError,
    the row is counted as failed by the import pipeline, nothing is written).
  - "warning" issues don't block the import; the claim is persisted and the
    warnings are saved as ClaimValidationIssue rows for later review.
"""

from app.canonical.claim import CanonicalClaim
from app.validation.issue import ValidationIssue
from app.validation.rules import ALL_RULES


class ValidationEngine:
    def run(self, claim: CanonicalClaim) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for rule in ALL_RULES:
            issues.extend(rule(claim))
        return issues

    @staticmethod
    def blocking_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
        return [issue for issue in issues if issue.severity == "error"]

    @staticmethod
    def warnings(issues: list[ValidationIssue]) -> list[ValidationIssue]:
        return [issue for issue in issues if issue.severity == "warning"]
