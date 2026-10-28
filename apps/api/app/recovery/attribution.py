from sqlalchemy.orm import Session

from app.recovery.lifecycle import RecoveryLifecycleService
from app.recovery.models import RecoveryAccount
from app.recovery.repository import RecoveryRepository
from app.recovery.schemas import LifecycleEventRead


class RecoveryTimelineService:
    def __init__(
        self,
        db: Session,
        organization_id: int,
        currency: str,
    ) -> None:
        self.repository = RecoveryRepository(db, organization_id)
        self.lifecycle = RecoveryLifecycleService(db, organization_id, currency)

    def timeline(
        self,
        account: RecoveryAccount,
        *,
        synchronize: bool = True,
        actor_id: int | None = None,
        correlation_id: str | None = None,
    ) -> list[LifecycleEventRead]:
        if synchronize:
            self.lifecycle.synchronize_verified_recoveries(
                account,
                actor_id=actor_id,
                actor_type="system",
                correlation_id=correlation_id,
            )
        return [
            LifecycleEventRead.model_validate(event) for event in self.repository.events(account.id)
        ]
