from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.governance.audit.service import AuditService
from app.models.user import User
from app.platform_admin.repository import PlatformAdminRepository


class PlatformAdminService:
    def __init__(self, db: Session, actor: User):
        self.db = db
        self.actor = actor
        self.repository = PlatformAdminRepository(db)
        self.audit = AuditService(db)

    def summary(self) -> dict:
        result = {
            "customers": self.repository.customer_metrics(),
            "platform": self.repository.platform_metrics(),
            "atlas_revenue": self.repository.atlas_revenue_metrics(),
            "ai_operations": self.repository.ai_operations(),
            "integration_errors": self.repository.integration_error_count(),
            "system_health": {
                "api": "healthy",
                "database": "healthy",
                "redis": "not_instrumented",
                "workers": "not_instrumented",
                "object_storage": "not_instrumented",
                "ai_providers": "not_instrumented",
            },
            "alerts": self.repository.alerts(),
            "unavailable_metrics": [
                "MRR and ARR",
                "implementation and enterprise fees",
                "customer health and churn risk",
                "support tickets",
                "AI failed request count",
                "queue depth and worker utilization",
            ],
        }
        self._audit("summary")
        return result

    def hospitals(self) -> list[dict]:
        result = self.repository.hospitals()
        self._audit("hospitals")
        return result

    def _audit(self, scope: str) -> None:
        self.audit.log(
            organization_id=self.actor.organization_id,
            user_id=self.actor.id,
            action=AuditAction.PLATFORM_ADMIN_VIEWED,
            entity="platform_admin",
            reason="Atlas platform administration access",
            metadata={"scope": scope, "access_mode": "aggregate_only"},
        )
        self.db.commit()
