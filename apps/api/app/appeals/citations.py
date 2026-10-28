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
    """Combine the AI's self-reported citations with KB-grounded ones the
    Citation Engine already knows are applicable for this denial category,
    deduping by (source, reference) so the same guideline isn't listed twice."""
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for entry in ai_citations or []:
        if not isinstance(entry, dict):
            continue
        key = (str(entry.get("source", "")).strip(), str(entry.get("reference", "")).strip())
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)

    for citation in kb_citations:
        key = (citation.source, citation.reference)
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "source": citation.source,
                "reference": citation.reference,
                "relevance": citation.description,
            }
        )

    return merged
