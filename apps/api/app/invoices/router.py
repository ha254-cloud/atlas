from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.invoices.schemas import InvoiceCreditNoteRead, InvoicePeriodRequest, InvoiceRead
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
