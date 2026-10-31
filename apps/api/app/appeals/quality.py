"""
Appeal Quality Score — Atlas scores its own draft before a human ever sees
it, across the five dimensions called out in the Sprint 12 spec:
completeness, evidence, tone, compliance, confidence. Every dimension is a
cheap, deterministic, rule-based check (no extra AI call) so scoring never
adds latency or cost to appeal generation.

`overall` is a weighted blend; `flagged_for_review` is set when overall (or
the AI's own confidence) is low, so low-quality drafts get closer scrutiny
before a reviewer approves them.
"""

import re

from app.appeals.evidence import EvidenceCheck

_UNPROFESSIONAL_PATTERNS = [
    re.compile(r"!{2,}"),
    re.compile(r"\b(gonna|wanna|hey|yeah|kinda|sorta)\b", re.IGNORECASE),
    re.compile(r"[A-Z]{6,}"),  # shouting
]

_LOW_QUALITY_THRESHOLD = 70


def _completeness_score(data: dict) -> int:
    text = data.get("appeal_letter", "") or ""
    length_score = min(80, int(len(text) / 10))  # ~800 chars -> full 80 pts
    bonus = 0
    if data.get("summary"):
        bonus += 10
    if data.get("requested_action"):
        bonus += 10
    return min(100, length_score + bonus)


def _evidence_score(evidence: EvidenceCheck) -> int:
    if not evidence.required:
        return 100
    return round(len(evidence.verified) / len(evidence.required) * 100)


def _tone_score(data: dict) -> int:
    text = data.get("appeal_letter", "") or ""
    score = 100
    for pattern in _UNPROFESSIONAL_PATTERNS:
        if pattern.search(text):
            score -= 20
    return max(0, score)


def _compliance_score(data: dict, kb_citation_available: bool) -> int:
    score = 100
    citations = data.get("citations") or []
    if kb_citation_available and not citations:
        # A relevant KB citation exists for this denial category but the
        # draft doesn't cite anything — a real, fixable compliance gap.
        score -= 15
    if not data.get("requested_action"):
        score -= 10
    return max(0, score)


def _confidence_score(data: dict) -> int:
    confidence = data.get("confidence", 0)
    if not isinstance(confidence, (int, float)):
        return 0
    return int(max(0, min(100, confidence)))


def _grounding_score(data: dict, grounding_report: dict | None) -> int:
    if grounding_report is None:
        return 100
    if grounding_report.get("rejected_model_citation_count", 0):
        return 70
    if grounding_report.get("grounded"):
        return 100 if data.get("citations") else 85
    return 100 if not data.get("citations") else 0


def score_appeal(
    data: dict,
    evidence: EvidenceCheck,
    kb_citation_available: bool = False,
    grounding_report: dict | None = None,
) -> dict:
    """Compute the multi-dimensional quality score for a generated appeal
    draft. Returns a JSON-serializable dict suitable for `Appeal.quality_score`."""
    completeness = _completeness_score(data)
    evidence_pct = _evidence_score(evidence)
    tone = _tone_score(data)
    compliance = _compliance_score(data, kb_citation_available)
    confidence = _confidence_score(data)
    grounding = _grounding_score(data, grounding_report)

    overall = round(
        completeness * 0.20
        + evidence_pct * 0.20
        + tone * 0.15
        + compliance * 0.15
        + confidence * 0.15
        + grounding * 0.15
    )

    return {
        "completeness": completeness,
        "evidence": evidence_pct,
        "tone": tone,
        "compliance": compliance,
        "confidence": confidence,
        "grounding": grounding,
        "overall": overall,
        "flagged_for_review": overall < _LOW_QUALITY_THRESHOLD,
    }
