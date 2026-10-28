"""
Validate AI-generated appeal output before persisting it.
Never store invalid or suspicious AI output in the database.
"""

import json
import re
from typing import Any


class AppealValidationError(Exception):
    pass


def _normalize(text: str) -> str:
    """Loose comparison key: uppercase, strip hyphens/spaces — mirrors
    DenialCodeRepository.normalize_code() so 'CO-16' == 'CO16' == 'co 16'."""
    return re.sub(r"[-\s]", "", text).upper()


def parse_ai_response(raw: str) -> dict[str, Any]:
    """
    Parse the AI's JSON response, handling common formatting issues
    (markdown code fences, leading/trailing prose).
    """
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", raw).strip()

    # Find the first { ... } block
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise AppealValidationError("AI response contains no JSON object")

    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError as exc:
        raise AppealValidationError(f"Invalid JSON in AI response: {exc}") from exc


def validate_appeal(
    data: dict[str, Any],
    claim_number: str,
    denial_code: str | None = None,
    patient_last_name: str | None = None,
) -> None:
    """
    Validate that the parsed appeal data has all required fields and that
    the appeal text meets minimum quality/compliance standards before it's
    ever shown to a reviewer:
      - present and long enough to be substantive
      - references the real claim number
      - references the actual denial code being appealed (not a different one)
      - mentions the real patient's name (a cheap but real guard against the
        AI having hallucinated/confused a different patient's details)
    """
    appeal_text = data.get("appeal_letter", "")

    if not appeal_text or len(appeal_text.strip()) < 200:
        raise AppealValidationError("Generated appeal letter is too short to be valid.")

    # The appeal should mention the claim number
    if claim_number and claim_number not in appeal_text:
        raise AppealValidationError(
            f"Appeal letter does not reference claim number {claim_number}."
        )

    # The appeal should reference the denial code it's actually appealing —
    # a missing reference is a sign the AI reasoned about the wrong denial.
    # Compared loosely (case/hyphen-insensitive) since the model may render
    # a code like "CO-16" as "CO16".
    if denial_code and _normalize(denial_code) not in _normalize(appeal_text):
        raise AppealValidationError(f"Appeal letter does not reference denial code {denial_code}.")

    # The appeal should mention the real patient by name — never silently
    # accept a letter that appears to be about someone else.
    if patient_last_name and patient_last_name.upper() not in appeal_text.upper():
        raise AppealValidationError(
            f"Appeal letter does not mention patient {patient_last_name} — "
            "possible hallucinated or mismatched patient information."
        )

    # Confidence must be a reasonable number
    confidence = data.get("confidence", 0)
    if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 100):
        data["confidence"] = 0

    # Ensure list fields are actually lists
    for list_field in ("key_arguments", "citations", "attachments", "missing_information"):
        if not isinstance(data.get(list_field), list):
            data[list_field] = []

    # A human-readable title is always present, even if the AI omitted one.
    if not data.get("title"):
        data["title"] = f"Appeal Letter — Claim {claim_number}"


def validate_sections(sections: dict[str, str], required: list[str]) -> None:
    """
    Quality check for the sectioned appeal path: every required section must
    be present and non-trivial, with no obvious unfilled template artifacts
    left behind by the model (e.g. "{claim_number}", "TODO", "[placeholder]").
    """
    for name in required:
        text = (sections.get(name) or "").strip()
        if len(text) < 10:
            raise AppealValidationError(f"Appeal section '{name}' is missing or too short.")
        if re.search(r"\{[a-z_]+\}|\bTODO\b|\[placeholder\]", text, re.IGNORECASE):
            raise AppealValidationError(
                f"Appeal section '{name}' contains an unfilled template artifact."
            )
