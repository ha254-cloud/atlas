from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.finance.schemas import (
    CashForecast,
    DenialLeakageItem,
    ExecutiveFinanceSnapshot,
    FinanceOverview,
    PayerFinanceScorecard,
)
from app.finance.service import FinanceIntelligenceService
from app.models.user import User
from app.organizations.entitlements import Feature, require_feature
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(
    prefix="/finance",
    tags=["Finance Intelligence"],
    dependencies=[Depends(require_feature(Feature.ANALYTICS))],
)


@router.get("/overview", response_model=FinanceOverview)
def overview(
    forecast_days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
) -> FinanceOverview:
    return FinanceIntelligenceService(db, organization_id).overview(forecast_days)


@router.get("/executive", response_model=ExecutiveFinanceSnapshot)
def executive_snapshot(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
) -> ExecutiveFinanceSnapshot:
    return FinanceIntelligenceService(db, organization_id).executive_snapshot()


@router.get("/payers", response_model=list[PayerFinanceScorecard])
def payer_scorecards(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
) -> list[PayerFinanceScorecard]:
    return FinanceIntelligenceService(db, organization_id).payer_scorecards()


@router.get("/denial-leakage", response_model=list[DenialLeakageItem])
def denial_leakage(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
) -> list[DenialLeakageItem]:
    return FinanceIntelligenceService(db, organization_id).denial_leakage()


@router.get("/forecast", response_model=CashForecast)
def forecast(
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
) -> CashForecast:
    return FinanceIntelligenceService(db, organization_id).forecast(days)
