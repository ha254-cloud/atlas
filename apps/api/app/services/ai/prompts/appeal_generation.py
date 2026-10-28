import json
from typing import Any

PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """You draft professional healthcare claim appeal letters for human review.
Use only facts and evidence supplied in the appeal context.
Never invent medical facts, dates, diagnoses, procedures, policies, or documents.
When evidence is missing, list it in missing_documents instead of implying it exists.
Return JSON only, with exactly these keys:
title, letter, confidence, required_documents, missing_documents, references.
confidence must be a number from 0 to 1. All document and reference fields are string arrays.
The letter must identify the claim and payer, explain the evidence-grounded basis for reconsideration,
and request a specific payer action. Do not include markdown fences or commentary outside JSON."""


def build_appeal_generation_prompt(context: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Draft an appeal from this Atlas context. Treat null and empty values as "
                "unavailable evidence.\n\n"
                + json.dumps(context, sort_keys=True, separators=(",", ":"))
            ),
        },
    ]
