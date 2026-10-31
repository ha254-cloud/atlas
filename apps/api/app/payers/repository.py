from __future__ import annotations

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.payers.models import Payer, PayerPolicySource


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

    def list_policy_sources(self, payer_id: int) -> list[PayerPolicySource]:
        return (
            self.db.query(PayerPolicySource)
            .filter(
                PayerPolicySource.organization_id == self.organization_id,
                PayerPolicySource.payer_id == payer_id,
            )
            .order_by(PayerPolicySource.policy_code, PayerPolicySource.version.desc())
            .all()
        )

    def get_policy_source(self, payer_id: int, source_id: int) -> PayerPolicySource | None:
        return (
            self.db.query(PayerPolicySource)
            .filter(
                PayerPolicySource.id == source_id,
                PayerPolicySource.payer_id == payer_id,
                PayerPolicySource.organization_id == self.organization_id,
            )
            .first()
        )

    def approved_policy_sources(
        self,
        payer_id: int,
        *,
        on_date: date,
    ) -> list[PayerPolicySource]:
        return (
            self.db.query(PayerPolicySource)
            .filter(
                PayerPolicySource.payer_id == payer_id,
                PayerPolicySource.organization_id == self.organization_id,
                PayerPolicySource.status == "approved",
                PayerPolicySource.jurisdiction == "KE",
                PayerPolicySource.effective_from <= on_date,
                or_(
                    PayerPolicySource.effective_to.is_(None),
                    PayerPolicySource.effective_to >= on_date,
                ),
            )
            .order_by(PayerPolicySource.policy_code, PayerPolicySource.version.desc())
            .all()
        )
