from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.billing.service import RecoveryFeeScheduleService
from app.documents.storage import read_file, save_bytes
from app.invoices.pdf import InvoicePDFService
from app.invoices.repository import InvoiceRepository
from app.models.invoice import Invoice, InvoiceCreditNote, InvoiceLine, InvoiceStatus
from app.models.organization import Organization
from app.payments.models import PaymentAllocation
from app.recoveries.repository import RecoveryRepository
from app.services.email_service import EmailService

_MONEY = Decimal("0.01")


class InvoiceService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id
        self.repository = InvoiceRepository(db, organization_id)
        self.recoveries = RecoveryRepository(db, organization_id)

    def generate_monthly(self, year: int, month: int) -> Invoice:
        period_start = date(year, month, 1)
        period_end = date(year, month, monthrange(year, month)[1])
        existing = self.repository.for_period(period_start, period_end)
        if existing is not None:
            return existing

        recoveries = self.recoveries.verified_uninvoiced(period_start, period_end)
        if not recoveries:
            raise ValueError("No verified, uninvoiced recoveries exist for this period")

        schedules = [
            RecoveryFeeScheduleService(self.db, self.organization_id).effective_on(
                recovery.payment_date
            )
            for recovery in recoveries
        ]
        currencies = {recovery.payment.currency for recovery in recoveries}
        vat_percentages = {schedule.vat_percentage for schedule in schedules}
        payment_terms = {schedule.payment_terms_days for schedule in schedules}
        if len(currencies) != 1:
            raise ValueError("Recoveries with different currencies require separate invoices")
        if len(vat_percentages) != 1:
            raise ValueError("Recoveries with different VAT rates require separate invoices")
        if len(payment_terms) != 1:
            raise ValueError("Recoveries with different payment terms require separate invoices")

        organization = self.db.query(Organization).filter(
            Organization.id == self.organization_id
        ).one()
        total_recovered = sum(
            (row.recovered_amount for row in recoveries), Decimal("0")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        total_fee = sum(
            (row.atlas_fee_amount for row in recoveries), Decimal("0")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        vat_percentage = vat_percentages.pop()
        vat_amount = (
            total_fee * vat_percentage / Decimal("100")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        payment_terms_days = payment_terms.pop()

        invoice = Invoice(
            organization_id=self.organization_id,
            invoice_number=f"ATL-{self.organization_id}-{year:04d}{month:02d}",
            period_start=period_start,
            period_end=period_end,
            status=InvoiceStatus.DRAFT,
            total_recovered_amount=total_recovered,
            total_fee_amount=total_fee,
            vat_percentage=vat_percentage,
            vat_amount=vat_amount,
            total_amount=total_fee + vat_amount,
            currency=currencies.pop(),
            payment_terms_days=payment_terms_days,
            due_date=period_end + timedelta(days=payment_terms_days),
            billing_name=organization.name,
            billing_email=organization.email,
        )
        self.db.add(invoice)
        self.db.flush()
        for recovery in recoveries:
            invoice.lines.append(InvoiceLine(
                recovery_id=recovery.id,
                payment_id=recovery.payment_id,
                claim_id=recovery.claim_id,
                payment_date=recovery.payment_date,
                recovered_amount=recovery.recovered_amount,
                fee_percentage=recovery.atlas_fee_percentage,
                fee_amount=recovery.atlas_fee_amount,
            ))
        self.db.flush()
        pdf_path, _ = save_bytes(
            InvoicePDFService.render(invoice),
            self.organization_id,
            ".pdf",
        )
        invoice.pdf_path = pdf_path
        invoice.pdf_generated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def mark_sent(self, invoice_id: int) -> Invoice:
        invoice = self.get(invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Only draft invoices can be sent")
        invoice.status = InvoiceStatus.SENT
        invoice.sent_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(invoice)
        organization = self.db.query(Organization).filter(
            Organization.id == self.organization_id
        ).one()
        breakdown = "\n".join(
            f"Claim {line.claim_id}: recovered {line.recovered_amount}, "
            f"Atlas fee {line.fee_amount} ({line.fee_percentage}%)"
            for line in invoice.lines
        )
        attachment = read_file(invoice.pdf_path) if invoice.pdf_path else None
        EmailService().send_custom(
            to=organization.email,
            subject=f"Atlas recovery invoice {invoice.invoice_number}",
            body=(
                f"Recovery period: {invoice.period_start} to {invoice.period_end}\n"
                f"Total recovered: {invoice.total_recovered_amount}\n"
                f"Atlas fees: {invoice.total_fee_amount}\n"
                f"VAT: {invoice.vat_amount}\n"
                f"Amount due: {invoice.total_amount} {invoice.currency}\n\n"
                f"Claim breakdown:\n{breakdown}"
            ),
            attachments=(
                [(f"{invoice.invoice_number}.pdf", attachment, "application/pdf")]
                if attachment else None
            ),
        )
        return invoice

    def mark_paid(self, invoice_id: int) -> Invoice:
        invoice = self.get(invoice_id)
        if invoice.status != InvoiceStatus.SENT:
            raise ValueError("Only sent invoices can be marked paid")
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def get(self, invoice_id: int) -> Invoice:
        invoice = self.repository.get(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice {invoice_id} not found")
        return invoice

    def list(self) -> list[Invoice]:
        return self.repository.list()

    def list_credit_notes(self) -> list[InvoiceCreditNote]:
        return self.repository.list_credit_notes()

    def create_credit_note_for_adjustment(
        self,
        *,
        recovery,
        allocation: PaymentAllocation,
        issued_by: int,
        reason: str,
        correlation_id: str,
    ) -> InvoiceCreditNote | None:
        invoice_line = recovery.invoice_line
        if invoice_line is None:
            return None
        existing = self.repository.credit_note_for_allocation(allocation.id)
        if existing is not None:
            return existing

        invoice = invoice_line.invoice
        fee_adjustment = (
            allocation.amount * invoice_line.fee_percentage / Decimal("100")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        vat_adjustment = (
            fee_adjustment * invoice.vat_percentage / Decimal("100")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        credit_note = InvoiceCreditNote(
            organization_id=self.organization_id,
            invoice_id=invoice.id,
            invoice_line_id=invoice_line.id,
            payment_allocation_id=allocation.id,
            credit_note_number=f"ATL-CN-{self.organization_id}-{allocation.id}",
            adjustment_type=allocation.allocation_type,
            recovered_adjustment_amount=allocation.amount,
            fee_adjustment_amount=fee_adjustment,
            vat_adjustment_amount=vat_adjustment,
            total_credit_amount=fee_adjustment + vat_adjustment,
            currency=invoice.currency,
            reason=reason,
            issued_by=issued_by,
            correlation_id=correlation_id,
        )
        self.db.add(credit_note)
        self.db.flush()
        return credit_note

    def pdf(self, invoice_id: int) -> tuple[str, bytes]:
        invoice = self.get(invoice_id)
        if not invoice.pdf_path:
            raise ValueError(f"Invoice {invoice_id} has no generated PDF")
        return f"{invoice.invoice_number}.pdf", read_file(invoice.pdf_path)
