"""
Pre-submission validation rules.

Each rule takes a CanonicalClaim (already normalized from CSV/FHIR/X12/etc.)
and returns zero or more ValidationIssue findings. Rules never raise and
never touch the database — the ValidationEngine decides what to do with
the findings (block vs. persist-as-warning).
"""

import re
from datetime import date

from app.canonical.claim import CanonicalClaim
from app.validation.issue import ValidationIssue

# CPT codes are 5 digits. HCPCS Level II codes are one letter + 4 digits.
CPT_PATTERN = re.compile(r"^\d{5}$")
HCPCS_PATTERN = re.compile(r"^[A-Z]\d{4}$")

# ICD-10-CM format: letter, digit, alphanumeric, optional ".", up to 4 more
# alphanumeric characters (e.g. "E11.9", "S72.001A").
ICD10_PATTERN = re.compile(r"^[A-TV-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$")

# CPT codes that frequently get denied when billed without a modifier —
# same-day E/M with a procedure (25), professional/technical split (26/TC),
# bilateral procedures (50), or distinct procedural service (59).
MODIFIER_REQUIRED_CPT_CODES = {
    "99213",
    "99214",
    "99215",
    "70450",
    "70460",
    "70470",
    "29880",
    "29881",
    "93000",
    "93005",
    "93010",
}

TIMELY_FILING_DAYS = 365


def check_amounts(claim: CanonicalClaim) -> list[ValidationIssue]:
    issues = []
    if claim.billed_amount <= 0:
        issues.append(
            ValidationIssue(
                code="INVALID_BILLED_AMOUNT",
                severity="error",
                field="billed_amount",
                message="Billed amount must be greater than zero.",
            )
        )
    if claim.paid_amount < 0:
        issues.append(
            ValidationIssue(
                code="INVALID_PAID_AMOUNT",
                severity="error",
                field="paid_amount",
                message="Paid amount cannot be negative.",
            )
        )
    if claim.paid_amount > claim.billed_amount:
        issues.append(
            ValidationIssue(
                code="OVERPAYMENT",
                severity="warning",
                field="paid_amount",
                message=(
                    f"Paid amount (${claim.paid_amount}) exceeds billed amount "
                    f"(${claim.billed_amount})."
                ),
            )
        )
    return issues


def check_diagnosis_codes(claim: CanonicalClaim) -> list[ValidationIssue]:
    issues = []
    if not claim.diagnosis_codes:
        issues.append(
            ValidationIssue(
                code="MISSING_DIAGNOSIS",
                severity="warning",
                field="diagnosis_codes",
                message="No ICD-10 diagnosis code was submitted with this claim.",
            )
        )
    for code in claim.diagnosis_codes:
        if not ICD10_PATTERN.match(code.upper()):
            issues.append(
                ValidationIssue(
                    code="INVALID_ICD10_FORMAT",
                    severity="error",
                    field="diagnosis_codes",
                    message=f"'{code}' is not a valid ICD-10-CM code format.",
                )
            )
    return issues


def check_procedure_codes(claim: CanonicalClaim) -> list[ValidationIssue]:
    issues = []
    for code in claim.procedure_codes:
        normalized = code.upper()
        if not (CPT_PATTERN.match(normalized) or HCPCS_PATTERN.match(normalized)):
            issues.append(
                ValidationIssue(
                    code="INVALID_CPT_FORMAT",
                    severity="error",
                    field="procedure_codes",
                    message=f"'{code}' is not a valid CPT/HCPCS code format.",
                )
            )
        elif normalized in MODIFIER_REQUIRED_CPT_CODES and not claim.modifiers:
            issues.append(
                ValidationIssue(
                    code="MISSING_MODIFIER",
                    severity="warning",
                    field="modifiers",
                    message=(
                        f"CPT {code} commonly requires a modifier (e.g. 25, "
                        "26/TC, 50, 59) — none was submitted."
                    ),
                )
            )
    return issues


def check_payer(claim: CanonicalClaim) -> list[ValidationIssue]:
    issues = []
    if not claim.payer_code or not claim.payer_code.strip():
        issues.append(
            ValidationIssue(
                code="MISSING_PAYER_CODE",
                severity="error",
                field="payer_code",
                message="Payer code is required.",
            )
        )
    return issues


def check_timely_filing(claim: CanonicalClaim, today: date | None = None) -> list[ValidationIssue]:
    today = today or date.today()
    age_days = (today - claim.service_date).days
    if age_days > TIMELY_FILING_DAYS:
        return [
            ValidationIssue(
                code="TIMELY_FILING_RISK",
                severity="warning",
                field="service_date",
                message=(
                    f"Service date is {age_days} days old — may be past the "
                    f"typical {TIMELY_FILING_DAYS}-day timely filing window."
                ),
            )
        ]
    return []


def check_authorization(claim: CanonicalClaim) -> list[ValidationIssue]:
    if (
        claim.authorization_expiration is not None
        and claim.authorization_expiration < claim.service_date
    ):
        return [
            ValidationIssue(
                code="AUTHORIZATION_EXPIRED",
                severity="error",
                field="authorization_expiration",
                message=(
                    f"Authorization expired on {claim.authorization_expiration}, "
                    f"before the service date {claim.service_date}."
                ),
            )
        ]
    return []


ALL_RULES = [
    check_amounts,
    check_diagnosis_codes,
    check_procedure_codes,
    check_payer,
    check_timely_filing,
    check_authorization,
]
