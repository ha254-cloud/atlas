from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.dashboard.analytics import AnalyticsRepository
from app.dashboard.schemas import DashboardResponse
from app.dashboard.service import DashboardService
from app.db.database import get_db
from app.models.user import User
from app.organizations.entitlements import Feature, require_feature
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_feature(Feature.ANALYTICS))],
)


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
) -> DashboardResponse:
    """
    Single endpoint that powers the entire dashboard.
    Returns metrics, recent claims, recent imports, and monthly trend data.
    All data is scoped to the authenticated user's organization.
    """
    return DashboardService(db, organization_id).get_dashboard()


@router.get("/analytics/denials")
def denial_breakdown(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return AnalyticsRepository(db, organization_id).denial_breakdown()


@router.get("/analytics/recovery-by-payer")
def recovery_by_payer(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return AnalyticsRepository(db, organization_id).recovery_by_payer()


@router.get("/analytics/recovery-rate")
def recovery_rate(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return AnalyticsRepository(db, organization_id).recovery_rate_summary()


@router.get("/analytics/executive-summary")
def executive_summary(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return AnalyticsRepository(db, organization_id).executive_summary()


@router.get("/analytics/financial-kpis")
def financial_kpis(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return AnalyticsRepository(db, organization_id).financial_kpis()


@router.get("/analytics/payer-performance")
def payer_performance(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return AnalyticsRepository(db, organization_id).payer_performance()


@router.get("/analytics/analyst-performance")
def analyst_performance(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return AnalyticsRepository(db, organization_id).analyst_performance()


@router.get("/analytics/appeals")
def appeal_dashboard(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    """Sprint 12 Appeal Dashboard metrics: appeals generated today, ready
    for submission, waiting on documents, waiting on approval, and the
    estimated recoverable revenue tied up in in-flight appeals."""
    return AnalyticsRepository(db, organization_id).appeal_dashboard()


@router.get("/analytics/forecast")
def revenue_forecast(
    months: int = 3,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    return AnalyticsRepository(db, organization_id).revenue_forecast(months=months)


@router.get("/analytics/insights")
def insights(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    return AnalyticsRepository(db, organization_id).generate_insights()
