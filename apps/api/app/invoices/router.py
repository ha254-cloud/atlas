from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.invoices.schemas import (
    InvoiceCreditNoteRead,
    InvoicePeriodRequest,
    InvoiceRead,
    InvoiceReconciliationRead,
    InvoiceReconciliationRequest,
)
from app.invoices.service import InvoiceService
from app.models.user import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("/monthly", response_model=InvoiceRead)
def generate_monthly_invoice(
    payload: InvoicePeriodRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return InvoiceService(db, organization_id).generate_monthly(
            payload.year,
            payload.month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    return InvoiceService(db, organization_id).list()


@router.get("/credit-notes", response_model=list[InvoiceCreditNoteRead])
def list_invoice_credit_notes(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    return InvoiceService(db, organization_id).list_credit_notes()


@router.post(
    "/{invoice_id}/reconciliations",
    response_model=InvoiceReconciliationRead,
    status_code=status.HTTP_201_CREATED,
)
def reconcile_invoice(
    invoice_id: int,
    payload: InvoiceReconciliationRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    correlation_id = str(getattr(request.state, "request_id", None) or "unknown")
    try:
        run = InvoiceService(db, organization_id).reconcile(
            invoice_id,
            run_by=current_user.id,
            reason=payload.reason,
            correlation_id=correlation_id,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.INVOICE_RECONCILED,
            entity="invoice_reconciliation_run",
            entity_id=run.id,
            before_state=None,
            after_state={
                "invoice_id": run.invoice_id,
                "status": run.status,
                "expected_net_amount": str(run.expected_net_amount),
                "actual_net_amount": str(run.actual_net_amount),
                "discrepancy_count": run.discrepancy_count,
            },
            reason=run.reason,
            correlation_id=correlation_id,
        )
        db.commit()
        db.refresh(run)
    except ValueError as exc:
        db.rollback()
        code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    EventPublisher().publish(
        EventType.INVOICE_RECONCILED,
        {
            "organization_id": organization_id,
            "invoice_id": invoice_id,
            "reconciliation_run_id": run.id,
            "status": run.status,
            "discrepancy_count": run.discrepancy_count,
            "actor_id": current_user.id,
            "correlation_id": correlation_id,
        },
        organization_id=organization_id,
    )
    return run


@router.get(
    "/{invoice_id}/reconciliations",
    response_model=list[InvoiceReconciliationRead],
)
def list_invoice_reconciliations(
    invoice_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return InvoiceService(db, organization_id).reconciliation_runs(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return InvoiceService(db, organization_id).get(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        filename, content = InvoiceService(db, organization_id).pdf(invoice_id)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{invoice_id}/send", response_model=InvoiceRead)
def send_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return InvoiceService(db, organization_id).mark_sent(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{invoice_id}/paid", response_model=InvoiceRead)
def mark_invoice_paid(
    invoice_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return InvoiceService(db, organization_id).mark_paid(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
