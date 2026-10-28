"""
Evidence Collector — Step 5 of the Appeal Generation Engine.

Cross-references the denial code's knowledge-base `required_documents` list
(app.models.denial_code.DenialCode) against what Atlas actually knows is on
file for the claim — real uploaded evidence (app.models.document.Document,
the Evidence Library) when there is any, plus structural claim data as a
fallback signal (e.g. an authorization number on the claim implies an
authorization is on file even if no document was uploaded for it) — and
flags anything it can't corroborate as "needs verification" before an
appeal is generated, so a human confirms the real document is on hand
before the appeal is submitted, instead of finding out after a second
denial.

This is advisory, not a hard gate: it never blocks appeal generation, it
just attaches a checklist to the draft.
"""

from dataclasses import dataclass, field


class MissingEvidenceError(Exception):
    """Raised when appeal generation is run in strict (`require_evidence=True`)
    mode and required supporting documents can't be verified on file — the
    Sprint 12 "Missing Documents Detection" case where the correct answer is
    'cannot generate appeal' rather than drafting one anyway."""

    def __init__(self, missing_documents: list[str]):
        self.missing_documents = missing_documents
        super().__init__(
            "Cannot generate appeal — missing required documentation: "
            + ", ".join(missing_documents)
        )


# Keyword -> predicate. If a required-document string contains the keyword
# (case-insensitive), the predicate decides whether Atlas' structured claim
# data already corroborates it being on file.
_VERIFIABLE_SIGNALS = {
    "authorization": lambda claim: bool(claim.authorization_number),
    "auth": lambda claim: bool(claim.authorization_number),
    "diagnosis": lambda claim: bool(claim.diagnoses),
    "icd": lambda claim: bool(claim.diagnoses),
    "procedure": lambda claim: bool(claim.claim_lines),
    "cpt": lambda claim: bool(claim.claim_lines),
    "coding": lambda claim: bool(claim.claim_lines),
}


@dataclass
class EvidenceCheck:
    required: list = field(default_factory=list)
    verified: list = field(default_factory=list)
    needs_verification: list = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not self.needs_verification


class EvidenceCollector:
    """Flags likely-missing supporting documentation for a claim before an
    appeal is drafted, grounded in the denial code's knowledge-base entry."""

    def check(
        self, claim, denial_code_info: dict | None, documents: list | None = None
    ) -> EvidenceCheck:
        required = list((denial_code_info or {}).get("required_documents") or [])
        verified: list[str] = []
        needs_verification: list[str] = []

        uploaded_signals = [
            f"{doc.document_type.value} {doc.filename} {' '.join(doc.tags or [])}".lower()
            for doc in (documents or [])
        ]

        for doc in required:
            doc_lower = doc.lower()
            corroborated = any(
                keyword in doc_lower and predicate(claim)
                for keyword, predicate in _VERIFIABLE_SIGNALS.items()
            ) or any(_matches_uploaded_document(doc_lower, signal) for signal in uploaded_signals)
            (verified if corroborated else needs_verification).append(doc)

        return EvidenceCheck(
            required=required, verified=verified, needs_verification=needs_verification
        )


def _matches_uploaded_document(required_doc_lower: str, uploaded_signal: str) -> bool:
    """Loose keyword overlap between a required-document string (e.g.
    'Operative Report') and an uploaded document's type/filename/tags."""
    required_words = {w for w in required_doc_lower.replace("-", " ").split() if len(w) > 3}
    return any(word in uploaded_signal for word in required_words)
