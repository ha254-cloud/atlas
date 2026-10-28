import json
from typing import Any

PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = (
    "You are an expert healthcare revenue cycle analyst. "
    "Return only a valid JSON object with exactly these fields: "
    "risk_score (integer from 0 to 100), recovery_probability (number from 0 to 1), "
    "priority (one of low, medium, high, critical), confidence (number from 0 to 1), "
    "recommended_action (non-empty string), summary (non-empty string), and "
    "required_documents (array of strings). Do not include markdown or additional fields."
)


def build_claim_analysis_prompt(context: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(context, sort_keys=True, separators=(",", ":")),
        },
    ]
