from sqlalchemy.orm import Session

from app.payments.models import Payment, PaymentSource


class PaymentRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def get(self, payment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.organization_id == self.organization_id,
        ).first()

    def by_reference(
        self,
        source: PaymentSource,
        payment_reference: str,
    ) -> Payment | None:
        return self.db.query(Payment).filter(
            Payment.organization_id == self.organization_id,
            Payment.source == source,
            Payment.payment_reference == payment_reference,
        ).first()

    def list(self) -> list[Payment]:
        return self.db.query(Payment).filter(
            Payment.organization_id == self.organization_id
        ).order_by(Payment.payment_date.desc(), Payment.id.desc()).all()
