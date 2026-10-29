from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.documents.storage import read_file, save_bytes
from app.invoices.pdf import InvoicePDFService
from app.invoices.repository import InvoiceRepository
from app.models.invoice import (
    Invoice,
    InvoiceCreditNote,
    InvoiceLine,
    InvoiceReconciliationRun,
    InvoiceStatus,
)
from app.models.organization import Organization
from app.models.recovery_attribution import (
    RecoveryAttributionDisputeResolution,
    RecoveryAttributionVersion,
)
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

        rows = self.recoveries.attributable_uninvoiced(period_start, period_end)
        if not rows:
            raise ValueError(
                "No verified, eligible, uninvoiced recoveries exist for this period"
            )

        currencies = {attribution.currency for _, attribution in rows}
        vat_percentages = {attribution.vat_percentage for _, attribution in rows}
        payment_terms = {attribution.payment_terms_days for _, attribution in rows}
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
            (attribution.eligible_amount for _, attribution in rows),
            Decimal("0"),
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        total_fee = sum(
            (
                attribution.eligible_amount
                * attribution.fee_percentage
                / Decimal("100")
                for _, attribution in rows
            ),
            Decimal("0"),
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
        for recovery, attribution in rows:
            fee_amount = (
                attribution.eligible_amount
                * attribution.fee_percentage
                / Decimal("100")
            ).quantize(_MONEY, rounding=ROUND_HALF_UP)
            invoice.lines.append(InvoiceLine(
                recovery_id=recovery.id,
                payment_id=recovery.payment_id,
                claim_id=recovery.claim_id,
                attribution_version_id=attribution.id,
                payment_date=recovery.payment_date,
                recovered_amount=attribution.eligible_amount,
                fee_percentage=attribution.fee_percentage,
                fee_amount=fee_amount,
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

    def create_credit_note_for_attribution_resolution(
        self,
        *,
        recovery,
        resolution: RecoveryAttributionDisputeResolution,
        previous_eligible_amount: Decimal,
        issued_by: int,
        reason: str,
        correlation_id: str,
    ) -> InvoiceCreditNote | None:
        invoice_line = recovery.invoice_line
        if invoice_line is None:
            return None
        existing = self.repository.credit_note_for_attribution_resolution(
            resolution.id
        )
        if existing is not None:
            return existing
        recovered_adjustment = (
            previous_eligible_amount - resolution.eligible_amount
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        if recovered_adjustment <= 0:
            return None
        invoice = invoice_line.invoice
        fee_adjustment = (
            recovered_adjustment * invoice_line.fee_percentage / Decimal("100")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        vat_adjustment = (
            fee_adjustment * invoice.vat_percentage / Decimal("100")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        credit_note = InvoiceCreditNote(
            organization_id=self.organization_id,
            invoice_id=invoice.id,
            invoice_line_id=invoice_line.id,
            payment_allocation_id=None,
            attribution_resolution_id=resolution.id,
            credit_note_number=(
                f"ATL-CN-{self.organization_id}-ATTR-{resolution.id}"
            ),
            adjustment_type="attribution_dispute",
            recovered_adjustment_amount=recovered_adjustment,
            fee_adjustment_amount=fee_adjustment,
            vat_adjustment_amount=vat_adjustment,
            total_credit_amount=fee_adjustment + vat_adjustment,
            currency=invoice.currency,
            reason=reason.strip(),
            issued_by=issued_by,
            correlation_id=correlation_id,
        )
        self.db.add(credit_note)
        self.db.flush()
        return credit_note

    def reconcile(
        self,
        invoice_id: int,
        *,
        run_by: int,
        reason: str,
        correlation_id: str,
    ) -> InvoiceReconciliationRun:
        invoice = self.get(invoice_id)
        discrepancies: list[dict] = []
        line_details: list[dict] = []
        source_payment_amount = Decimal("0.00")
        expected_recovered = Decimal("0.00")
        expected_fee = Decimal("0.00")
        vat_percentages: set[Decimal] = set()

        for line in invoice.lines:
            attribution = line.attribution_version
            if attribution is None:
                discrepancies.append(
                    {
                        "type": "missing_attribution_version",
                        "invoice_line_id": line.id,
                    }
                )
                continue
            source_net = self.recoveries.net_allocated_for_recovery(line.recovery)
            source_payment_amount += source_net
            expected_recovered += attribution.eligible_amount
            line_expected_fee = (
                attribution.eligible_amount
                * attribution.fee_percentage
                / Decimal("100")
            ).quantize(_MONEY, rounding=ROUND_HALF_UP)
            expected_fee += line_expected_fee
            vat_percentages.add(attribution.vat_percentage)
            checks = {
                "confirmed_vs_allocation": (
                    attribution.confirmed_amount - source_net
                ).quantize(_MONEY),
                "line_recovered": (
                    line.recovered_amount - attribution.eligible_amount
                ).quantize(_MONEY),
                "line_fee": (line.fee_amount - line_expected_fee).quantize(_MONEY),
            }
            for check, difference in checks.items():
                if difference != 0:
                    discrepancies.append(
                        {
                            "type": check,
                            "invoice_line_id": line.id,
                            "difference": str(difference),
                        }
                    )
            if attribution.currency != invoice.currency:
                discrepancies.append(
                    {
                        "type": "currency_mismatch",
                        "invoice_line_id": line.id,
                        "expected": attribution.currency,
                        "actual": invoice.currency,
                    }
                )
            line_details.append(
                {
                    "invoice_line_id": line.id,
                    "recovery_id": line.recovery_id,
                    "attribution_version_id": attribution.id,
                    "source_net_allocation": str(source_net),
                    "confirmed_amount": str(attribution.confirmed_amount),
                    "eligible_amount": str(attribution.eligible_amount),
                    "expected_fee_amount": str(line_expected_fee),
                    "checks": {key: str(value) for key, value in checks.items()},
                }
            )

        expected_recovered = expected_recovered.quantize(_MONEY)
        expected_fee = expected_fee.quantize(_MONEY)
        if len(vat_percentages) != 1:
            discrepancies.append(
                {
                    "type": "vat_snapshot_count",
                    "count": len(vat_percentages),
                }
            )
            expected_vat = Decimal("0.00")
        else:
            expected_vat = (
                expected_fee * next(iter(vat_percentages)) / Decimal("100")
            ).quantize(_MONEY, rounding=ROUND_HALF_UP)

        expected_credit = Decimal("0.00")
        actual_credit = Decimal("0.00")
        credit_details: list[dict] = []
        for credit in self.repository.credit_notes_for_invoice(invoice.id):
            actual_credit += credit.total_credit_amount
            expected_recovered_adjustment = self._credit_recovered_adjustment(credit)
            expected_credit_fee = (
                expected_recovered_adjustment
                * credit.invoice_line.fee_percentage
                / Decimal("100")
            ).quantize(_MONEY, rounding=ROUND_HALF_UP)
            expected_credit_vat = (
                expected_credit_fee
                * credit.invoice.vat_percentage
                / Decimal("100")
            ).quantize(_MONEY, rounding=ROUND_HALF_UP)
            expected_total_credit = expected_credit_fee + expected_credit_vat
            expected_credit += expected_total_credit
            if credit.total_credit_amount != expected_total_credit:
                discrepancies.append(
                    {
                        "type": "credit_note_total",
                        "credit_note_id": credit.id,
                        "difference": str(
                            credit.total_credit_amount - expected_total_credit
                        ),
                    }
                )
            credit_details.append(
                {
                    "credit_note_id": credit.id,
                    "expected_total": str(expected_total_credit),
                    "actual_total": str(credit.total_credit_amount),
                }
            )

        actual_credit = actual_credit.quantize(_MONEY)
        expected_credit = expected_credit.quantize(_MONEY)
        expected_total = (expected_fee + expected_vat).quantize(_MONEY)
        expected_net = (expected_total - expected_credit).quantize(_MONEY)
        actual_net = (invoice.total_amount - actual_credit).quantize(_MONEY)
        header_checks = {
            "recovered_total": (
                invoice.total_recovered_amount - expected_recovered
            ).quantize(_MONEY),
            "fee_total": (invoice.total_fee_amount - expected_fee).quantize(_MONEY),
            "vat_total": (invoice.vat_amount - expected_vat).quantize(_MONEY),
            "invoice_total": (invoice.total_amount - expected_total).quantize(_MONEY),
            "net_total": (actual_net - expected_net).quantize(_MONEY),
        }
        for check, difference in header_checks.items():
            if difference != 0:
                discrepancies.append(
                    {"type": check, "difference": str(difference)}
                )
        discrepancy_amount = sum(
            (abs(value) for value in header_checks.values()),
            Decimal("0.00"),
        ).quantize(_MONEY)
        run = InvoiceReconciliationRun(
            organization_id=self.organization_id,
            invoice_id=invoice.id,
            status="reconciled" if not discrepancies else "discrepancy",
            source_payment_amount=source_payment_amount.quantize(_MONEY),
            expected_recovered_amount=expected_recovered,
            actual_recovered_amount=invoice.total_recovered_amount,
            expected_fee_amount=expected_fee,
            actual_fee_amount=invoice.total_fee_amount,
            expected_vat_amount=expected_vat,
            actual_vat_amount=invoice.vat_amount,
            credit_note_amount=actual_credit,
            expected_net_amount=expected_net,
            actual_net_amount=actual_net,
            discrepancy_amount=discrepancy_amount,
            discrepancy_count=len(discrepancies),
            currency=invoice.currency,
            details={
                "lines": line_details,
                "credit_notes": credit_details,
                "header_checks": {
                    key: str(value) for key, value in header_checks.items()
                },
                "discrepancies": discrepancies,
            },
            run_by=run_by,
            reason=reason.strip(),
            correlation_id=correlation_id,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def reconciliation_runs(
        self,
        invoice_id: int,
    ) -> list[InvoiceReconciliationRun]:
        self.get(invoice_id)
        return self.repository.reconciliation_runs(invoice_id)

    def _credit_recovered_adjustment(
        self,
        credit: InvoiceCreditNote,
    ) -> Decimal:
        if credit.payment_allocation_id is not None:
            return credit.payment_allocation.amount
        resolution = credit.attribution_resolution
        if resolution is None:
            return Decimal("0.00")
        disputed = resolution.dispute.attribution_version
        previous = self.db.query(RecoveryAttributionVersion).filter(
            RecoveryAttributionVersion.id == disputed.previous_version_id,
            RecoveryAttributionVersion.organization_id == self.organization_id,
        ).one()
        return (previous.eligible_amount - resolution.eligible_amount).quantize(
            _MONEY
        )

    def pdf(self, invoice_id: int) -> tuple[str, bytes]:
        invoice = self.get(invoice_id)
        if not invoice.pdf_path:
            raise ValueError(f"Invoice {invoice_id} has no generated PDF")
        return f"{invoice.invoice_number}.pdf", read_file(invoice.pdf_path)
