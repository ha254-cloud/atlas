"""
Regulatory citations and payer policy references used in appeal letters.
These are stored centrally so they can be updated as guidelines change.
"""

from dataclasses import dataclass

from app.models.denial import DenialType


@dataclass
class Citation:
    source: str
    reference: str
    description: str
    policy_source_id: int | None = None
    policy_code: str | None = None
    version: int | None = None
    content_sha256: str | None = None


# Jurisdiction-specific references must come from a reviewed, versioned
# knowledge pack. No US CMS references are valid Kenya defaults.
CITATION_INDEX: dict[str, Citation] = {}


def get_citation(key: str) -> Citation | None:
    return CITATION_INDEX.get(key)


DENIAL_TYPE_CITATION_KEYS: dict[DenialType, str] = {}


def citations_for_denial_type(denial_type: DenialType | None) -> list[Citation]:
    """The KB-grounded citation(s) applicable to a denial category, if any."""
    if denial_type is None:
        return []
    key = DENIAL_TYPE_CITATION_KEYS.get(denial_type)
    citation = get_citation(key) if key else None
    return [citation] if citation else []


def merge_citations(ai_citations: list | None, kb_citations: list[Citation]) -> list[dict]:
    """Return only citations present in the reviewed knowledge base.

    Model-proposed citations are untrusted. They may influence relevance text
    only when their source and reference exactly match a verified citation.
    """
    merged: list[dict] = []
    ai_by_key: dict[tuple[str, str], dict] = {}

    for entry in ai_citations or []:
        if not isinstance(entry, dict):
            continue
        key = (
            str(entry.get("source", "")).strip().casefold(),
            str(entry.get("reference", "")).strip().casefold(),
        )
        if all(key):
            ai_by_key[key] = entry

    for citation in kb_citations:
        key = (citation.source.strip().casefold(), citation.reference.strip().casefold())
        proposed = ai_by_key.get(key)
        merged.append(
            {
                "source": citation.source,
                "reference": citation.reference,
                "relevance": (
                    str(proposed.get("relevance", "")).strip()
                    if proposed and proposed.get("relevance")
                    else citation.description
                ),
                **(
                    {
                        "policy_source_id": citation.policy_source_id,
                        "policy_code": citation.policy_code,
                        "version": citation.version,
                        "content_sha256": citation.content_sha256,
                    }
                    if citation.policy_source_id is not None
                    else {}
                ),
            }
        )

    return merged
