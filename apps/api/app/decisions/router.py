from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.decisions.payer_stats_service import PayerStatisticsService
from app.decisions.queries import DecisionQueryService
from app.decisions.schemas import (
    ClaimDecisionRead,
    DecisionQueueResponse,
    ExecutiveForecast,
    PayerStatisticsRead,
)
from app.decisions.service import DecisionService
from app.models.payer_statistics import PayerStatistics
from app.models.user import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(tags=["Decision Intelligence"])


@router.post("/decisions/claims/{claim_id}/evaluate", response_model=ClaimDecisionRead)
def evaluate_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    try:
        return DecisionService(db, organization_id).evaluate_claim(claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/decisions/claims/{claim_id}", response_model=ClaimDecisionRead)
def get_latest_decision(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    decision = DecisionService(db, organization_id).get_latest_for_claim(claim_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="No decision recorded for this claim yet")
    return decision


@router.post("/decisions/evaluate-open", response_model=list[ClaimDecisionRead])
def evaluate_open_claims(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    return DecisionService(db, organization_id).evaluate_open_claims()


@router.get("/decisions/queue", response_model=DecisionQueueResponse)
def get_decision_queue(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return DecisionQueryService(db, organization_id).get_queue()


@router.get("/decisions/executive-forecast", response_model=ExecutiveForecast)
def get_executive_forecast(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return DecisionQueryService(db, organization_id).get_executive_forecast()


@router.post("/decisions/payer-statistics/refresh", response_model=list[PayerStatisticsRead])
def refresh_payer_statistics(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    return PayerStatisticsService(db, organization_id).refresh_all()


@router.get("/decisions/payer-statistics", response_model=list[PayerStatisticsRead])
def list_payer_statistics(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return (
        db.query(PayerStatistics).filter(PayerStatistics.organization_id == organization_id).all()
    )
