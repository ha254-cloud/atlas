"""
Multi-Agent Intelligence API surface (Sprint 4).

One endpoint: trigger the full agent orchestration for a claim and get
back every agent's output, any detected conflicts, and the final
decision. This is a deliberately separate, explicitly-triggered action
from the standard analyze-on-import pipeline (ClaimAnalysisService) —
it is NOT auto-wired into Celery's analyze_claim_task, so running it
never duplicates cost unless a user/analyst actually asks for it.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents.orchestrator import AgentOrchestrator
from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.organizations.entitlements import Feature, require_feature
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(
    prefix="/claims/{claim_id}/agents",
    tags=["Multi-Agent Intelligence"],
    dependencies=[Depends(require_feature(Feature.AI_ANALYSIS))],
)


@router.post("/analyze")
async def run_multi_agent_analysis(
    claim_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    """
    Run every specialist agent (Coding, Documentation, Compliance, Risk,
    Recovery, and — if Recovery recommends it — Appeal) against a claim,
    resolve any conflicts between them, and return the merged result.
    Also persisted onto the claim's ClaimAnalysis row
    (`multi_agent_result`) and logged per-agent to `agent_execution_logs`.
    """
    try:
        result = await AgentOrchestrator(db, organization_id).run(claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.AI_ANALYSIS_RUN,
        entity="claim",
        entity_id=claim_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return result
