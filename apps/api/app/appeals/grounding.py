"""Deterministic trust boundary for payer-policy grounding."""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

from app.appeals.citations import Citation
from app.appeals.validator import AppealValidationError
from app.core.config import settings

if TYPE_CHECKING:
    from app.payers.models import PayerPolicySource


_POLICY_ASSERTION_PATTERN = re.compile(
    r"\b(?:policy|guideline|regulation|contract|benefit schedule)\b"
    r"[^.!?\n]{0,160}\b(?:requires?|mandates?|states?|provides?|allows?|"
    r"prohibits?|entitles?|covers?|according)\b",
    re.IGNORECASE,
)
_SAFE_NO_SOURCE_STATEMENTS = (
    "payer policy verification is required",
    "no verified payer policy source was available",
)


def policy_source_citation(source: PayerPolicySource) -> Citation:
    return Citation(
        source=source.title,
        reference=source.source_reference,
        description=f"Approved Kenya payer source {source.policy_code}, version {source.version}.",
        policy_source_id=source.id,
        policy_code=source.policy_code,
        version=source.version,
        content_sha256=source.content_sha256,
    )


def policy_source_prompt_context(sources: list[PayerPolicySource]) -> list[dict]:
    remaining = settings.AI_APPEAL_POLICY_CONTEXT_MAX_CHARS
    result: list[dict] = []
    for source in sources:
        if remaining <= 0:
            break
        excerpt = source.content[: settings.AI_APPEAL_POLICY_SOURCE_MAX_CHARS]
        excerpt = excerpt[:remaining]
        remaining -= len(excerpt)
        result.append(
            {
                "id": source.id,
                "policy_code": source.policy_code,
                "title": source.title,
                "version": source.version,
                "reference": source.source_reference,
                "content_sha256": source.content_sha256,
                "excerpt": excerpt,
            }
        )
    return result


def render_policy_reference_section(policy_sources: list[dict]) -> str:
    if not policy_sources:
        return (
            "No verified payer policy source was available for this claim. "
            "Payer policy verification is required before submission."
        )
    lines = ["The following reviewed payer sources apply to this claim:"]
    for source in policy_sources:
        lines.append(
            f"- {source['title']} ({source['reference']}), "
            f"version {source['version']}: {source['excerpt']}"
        )
    return "\n".join(lines)


def validate_policy_assertions(text: str, *, has_verified_sources: bool) -> None:
    if has_verified_sources:
        return
    normalized = text
    for statement in _SAFE_NO_SOURCE_STATEMENTS:
        normalized = re.sub(re.escape(statement), "", normalized, flags=re.IGNORECASE)
    if _POLICY_ASSERTION_PATTERN.search(normalized):
        raise AppealValidationError(
            "Appeal contains a payer-policy assertion without an approved applicable source."
        )


def build_grounding_report(
    *,
    payer_id: int,
    service_date: date,
    denial_category: str | None,
    procedure_codes: set[str],
    sources: list[PayerPolicySource],
    model_citations: list | None,
    accepted_citations: list[dict],
) -> dict:
    accepted_keys = {
        (
            str(item.get("source", "")).strip().casefold(),
            str(item.get("reference", "")).strip().casefold(),
        )
        for item in accepted_citations
    }
    proposed_keys = {
        (
            str(item.get("source", "")).strip().casefold(),
            str(item.get("reference", "")).strip().casefold(),
        )
        for item in model_citations or []
        if isinstance(item, dict)
    }
    return {
        "jurisdiction": "KE",
        "payer_id": payer_id,
        "claim_service_date": service_date.isoformat(),
        "denial_category": denial_category,
        "procedure_codes": sorted(procedure_codes),
        "grounded": bool(sources),
        "policy_section_mode": "verified_sources" if sources else "verification_required",
        "source_count": len(sources),
        "sources": [
            {
                "id": source.id,
                "policy_code": source.policy_code,
                "title": source.title,
                "version": source.version,
                "source_reference": source.source_reference,
                "content_sha256": source.content_sha256,
                "effective_from": source.effective_from.isoformat(),
                "effective_to": (
                    source.effective_to.isoformat() if source.effective_to is not None else None
                ),
                "approved_at": (
                    source.approved_at.isoformat() if source.approved_at is not None else None
                ),
            }
            for source in sources
        ],
        "accepted_citation_count": len(accepted_keys),
        "rejected_model_citation_count": len(proposed_keys - accepted_keys),
    }
