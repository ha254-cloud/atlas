from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.eclaims.schemas import (
    SHAClaimSubmit,
    SHAExchangeRead,
    SHAExchangeRefresh,
)
from app.eclaims.service import SHAExchangeService
from app.integrations.connectors.sha import SHAConnectorError
from app.models.user import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/eclaims", tags=["SHA eClaims"])


@router.post(
    "/claims/{claim_id}/submit",
    response_model=SHAExchangeRead,
    status_code=201,
)
async def submit_sha_claim(
    claim_id: int,
    payload: SHAClaimSubmit,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.SUBMIT_CLAIMS)),
):
    try:
        return await SHAExchangeService(db, organization_id).submit(
            claim_id,
            payload,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SHAConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/claims/{claim_id}/exchanges",
    response_model=list[SHAExchangeRead],
)
def list_sha_claim_exchanges(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        return SHAExchangeService(db, organization_id).for_claim(claim_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/exchanges/{exchange_id}", response_model=SHAExchangeRead)
def get_sha_exchange(
    exchange_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        return SHAExchangeService(db, organization_id).get(exchange_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/exchanges/{exchange_id}/refresh",
    response_model=SHAExchangeRead,
)
async def refresh_sha_exchange(
    exchange_id: int,
    payload: SHAExchangeRefresh,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.SUBMIT_CLAIMS)),
):
    try:
        return await SHAExchangeService(db, organization_id).refresh(
            exchange_id,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            reason=payload.reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SHAConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
