from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models.invoice import Invoice, InvoiceCreditNote


class InvoiceRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def get(self, invoice_id: int) -> Invoice | None:
        return self.db.query(Invoice).options(joinedload(Invoice.lines)).filter(
            Invoice.id == invoice_id,
            Invoice.organization_id == self.organization_id,
        ).first()

    def for_period(self, period_start: date, period_end: date) -> Invoice | None:
        return self.db.query(Invoice).options(joinedload(Invoice.lines)).filter(
            Invoice.organization_id == self.organization_id,
            Invoice.period_start == period_start,
            Invoice.period_end == period_end,
        ).first()

    def list(self) -> list[Invoice]:
        return self.db.query(Invoice).options(joinedload(Invoice.lines)).filter(
            Invoice.organization_id == self.organization_id
        ).order_by(Invoice.period_start.desc()).all()

    def list_credit_notes(self) -> list[InvoiceCreditNote]:
        return (
            self.db.query(InvoiceCreditNote)
            .filter(InvoiceCreditNote.organization_id == self.organization_id)
            .order_by(InvoiceCreditNote.issued_at.desc(), InvoiceCreditNote.id.desc())
            .all()
        )

    def credit_note_for_allocation(
        self,
        allocation_id: int,
    ) -> InvoiceCreditNote | None:
        return (
            self.db.query(InvoiceCreditNote)
            .filter(
                InvoiceCreditNote.organization_id == self.organization_id,
                InvoiceCreditNote.payment_allocation_id == allocation_id,
            )
            .first()
        )
