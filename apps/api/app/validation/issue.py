from dataclasses import dataclass


@dataclass
class ValidationIssue:
    """
    A single finding from the pre-submission ValidationEngine.

    severity="error"   -> blocks the claim from being imported.
    severity="warning" -> claim is still imported, but the issue is
                           persisted (ClaimValidationIssue) for review.
    """

    code: str
    severity: str
    field: str
    message: str
