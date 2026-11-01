from sqlalchemy.orm import Session, joinedload, selectinload

from app.eclaims.models import SHAExchange
from app.models.claim import Claim
from app.models.integration import Integration
from app.models.organization import Organization


class SHAExchangeRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def claim(self, claim_id: int) -> Claim | None:
        return (
            self.db.query(Claim)
            .options(
                joinedload(Claim.patient),
                joinedload(Claim.payer),
                selectinload(Claim.claim_lines),
                selectinload(Claim.diagnoses),
            )
            .filter(
                Claim.id == claim_id,
                Claim.organization_id == self.organization_id,
            )
            .first()
        )

    def organization(self) -> Organization:
        return (
            self.db.query(Organization)
            .filter(Organization.id == self.organization_id)
            .one()
        )

    def integration(self, integration_id: int) -> Integration | None:
        return (
            self.db.query(Integration)
            .filter(
                Integration.id == integration_id,
                Integration.organization_id == self.organization_id,
            )
            .first()
        )

    def get(self, exchange_id: int) -> SHAExchange | None:
        return (
            self.db.query(SHAExchange)
            .filter(
                SHAExchange.id == exchange_id,
                SHAExchange.organization_id == self.organization_id,
            )
            .first()
        )

    def by_idempotency_key(self, idempotency_key: str) -> SHAExchange | None:
        return (
            self.db.query(SHAExchange)
            .filter(
                SHAExchange.organization_id == self.organization_id,
                SHAExchange.idempotency_key == idempotency_key,
            )
            .first()
        )

    def for_claim(self, claim_id: int) -> list[SHAExchange]:
        return (
            self.db.query(SHAExchange)
            .filter(
                SHAExchange.organization_id == self.organization_id,
                SHAExchange.claim_id == claim_id,
            )
            .order_by(SHAExchange.created_at.desc())
            .all()
        )
