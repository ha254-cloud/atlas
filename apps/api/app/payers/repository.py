from sqlalchemy.orm import Session

from app.payers.models import Payer


class PayerRepository:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def list(self, *, active_only: bool = True) -> list[Payer]:
        query = self.db.query(Payer).filter(Payer.organization_id == self.organization_id)
        if active_only:
            query = query.filter(Payer.is_active.is_(True))
        return query.order_by(Payer.name).all()

    def get(self, payer_id: int) -> Payer | None:
        return (
            self.db.query(Payer)
            .filter(
                Payer.id == payer_id,
                Payer.organization_id == self.organization_id,
            )
            .first()
        )

    def get_by_code(self, payer_code: str) -> Payer | None:
        return (
            self.db.query(Payer)
            .filter(
                Payer.organization_id == self.organization_id,
                Payer.payer_code == payer_code,
            )
            .first()
        )
