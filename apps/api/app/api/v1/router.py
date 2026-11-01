from fastapi import APIRouter

from app.api.v1.agents import router as agents_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_summary_router
from app.api.v1.denial_codes import router as denial_codes_router
from app.api.v1.imports import router as imports_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.payments import router as payments_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.users import router as users_router
from app.appeals.router import router as appeals_router
from app.branches.router import router as branches_router
from app.claims.router import router as claims_router
from app.copilot.router import router as copilot_router
from app.dashboard.router import router as dashboard_router
from app.decisions.router import router as decisions_router
from app.documents.router import router as documents_router
from app.eclaims.router import router as eclaims_router
from app.finance.router import router as finance_router
from app.governance.router import router as governance_router
from app.invoices.router import router as invoices_router
from app.mcp.server import router as mcp_router
from app.patients.router import router as patients_router
from app.payer_connectivity.router import router as payer_connectivity_router
from app.payers.router import router as payers_router
from app.platform_admin.router import router as platform_admin_router
from app.recoveries.router import router as recoveries_router
from app.recovery.router import router as recovery_router
from app.recovery_workspace.router import router as workspace_router
from app.submissions.router import router as submissions_router
from app.tasks.router import router as tasks_router
from app.webhooks.router import router as webhooks_router
from app.workflow_engine.router import router as workflow_engine_router
from app.workflows.router import router as workflows_router

router = APIRouter(tags=["API v1"])

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(organizations_router)
router.include_router(onboarding_router)
router.include_router(imports_router)
router.include_router(uploads_router)
router.include_router(claims_router)
router.include_router(patients_router)
router.include_router(branches_router)
router.include_router(copilot_router)
router.include_router(appeals_router)
router.include_router(documents_router)
router.include_router(eclaims_router)
router.include_router(dashboard_router)
router.include_router(dashboard_summary_router)
router.include_router(denial_codes_router)
router.include_router(recovery_router)
router.include_router(workspace_router)
router.include_router(workflows_router)
router.include_router(workflow_engine_router)
router.include_router(notifications_router)
router.include_router(integrations_router)
router.include_router(payments_router)
router.include_router(audit_logs_router)
router.include_router(mcp_router)
router.include_router(payer_connectivity_router)
router.include_router(payers_router)
router.include_router(submissions_router)
router.include_router(recoveries_router)
router.include_router(invoices_router)
router.include_router(agents_router)
router.include_router(decisions_router)
router.include_router(webhooks_router)
router.include_router(finance_router)
router.include_router(governance_router)
router.include_router(tasks_router)
router.include_router(platform_admin_router)
