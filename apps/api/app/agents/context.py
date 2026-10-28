"""
ClaimContext — the single object every agent receives.

Built ONCE per orchestration run (see app.agents.orchestrator) by fetching
everything an agent might need up front, so individual agents never touch
the database directly for their own inputs (the Coding Agent "doesn't need
to fetch anything" — it just reads context.claim/context.documents/etc.,
per the Sprint 4 design).

`agent_outputs` is the one mutable piece: the orchestrator fills it in as
each phase completes, so later agents (Recovery, Appeal) can read earlier
agents' findings (Risk, Compliance) through the *same* context object
instead of needing a different method signature — every agent still only
ever receives `context`.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.claims.repository import ClaimRepository
from app.claims.timeline import ClaimTimeline
from app.models.claim_event import ClaimEvent
from app.models.denial import Denial
from app.models.organization import Organization
from app.models.recovery_case import RecoveryCase
from app.repositories.denial_code_repository import DenialCodeRepository


@dataclass
class ClaimContext:
    organization_id: int
    claim: object
    patient: object | None
    payer: object | None
    organization: Organization | None
    documents: list
    denial: Denial | None
    denial_code_info: dict | None
    analysis: object | None
    recovery_case: RecoveryCase | None
    history: list[ClaimEvent]
    agent_outputs: dict = field(default_factory=dict)


def _lookup_denial_code_info(db: Session, denial: Denial | None) -> dict | None:
    """Same knowledge-base grounding lookup ClaimAnalysisService uses for
    the single-call analyzer — duplicated here (rather than imported) to
    keep app.agents decoupled from app.services, since this is a small,
    stable, read-only query."""
    if denial is None:
        return None
    entry = DenialCodeRepository(db).get_by_code(denial.denial_code)
    if entry is None:
        return None
    return {
        "code": entry.code,
        "category": entry.category.value,
        "description": entry.description,
        "recovery_strategy": entry.recovery_strategy,
        "ai_guidance": entry.ai_guidance,
        "severity": entry.severity.value if entry.severity else None,
        "recoverability": entry.recoverability.value if entry.recoverability else None,
        "typical_recovery_rate": entry.typical_recovery_rate,
        "required_documents": entry.required_documents,
        "typical_resolution_days": entry.typical_resolution_days,
        "common_payers": entry.common_payers,
    }


def build_context(db: Session, organization_id: int, claim_id: int) -> ClaimContext:
    """Fetch a claim and everything an agent might want to know about it,
    exactly once, up front."""
    claim = ClaimRepository(db, organization_id).get(claim_id)
    if claim is None:
        raise ValueError(f"Claim {claim_id} not found")

    denial = (
        db.query(Denial)
        .filter(Denial.claim_id == claim_id, Denial.organization_id == organization_id)
        .order_by(Denial.id.desc())
        .first()
    )
    analysis = None
    from app.models.claim_analysis import ClaimAnalysis

    analysis = (
        db.query(ClaimAnalysis)
        .filter(
            ClaimAnalysis.claim_id == claim_id, ClaimAnalysis.organization_id == organization_id
        )
        .first()
    )
    recovery_case = (
        db.query(RecoveryCase)
        .filter(RecoveryCase.claim_id == claim_id, RecoveryCase.organization_id == organization_id)
        .order_by(RecoveryCase.id.desc())
        .first()
    )
    organization = db.query(Organization).filter(Organization.id == organization_id).first()

    return ClaimContext(
        organization_id=organization_id,
        claim=claim,
        patient=claim.patient,
        payer=claim.payer,
        organization=organization,
        documents=list(claim.documents or []),
        denial=denial,
        denial_code_info=_lookup_denial_code_info(db, denial),
        analysis=analysis,
        recovery_case=recovery_case,
        history=ClaimTimeline(db).get_timeline(claim_id, organization_id),
    )
